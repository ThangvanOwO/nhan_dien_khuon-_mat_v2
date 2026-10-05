import base64
import csv
import datetime
import functools
import io
import logging
import re
import shutil

import cv2
import numpy as np
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.http import HttpResponse, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from . import face_recognition as fr
from .attendance import record_student, student_for_identity, validate_confidence
from .models import (AttendanceRecord, AttendanceSession, Camera, ClassRoom,
                     Schedule, Student, Subject)

logger = logging.getLogger(__name__)


def api(methods):
    def decorate(function):
        @require_http_methods(methods)
        @functools.wraps(function)
        def wrapped(request, *args, **kwargs):
            try:
                return function(request, *args, **kwargs)
            except (ValueError, TypeError, ValidationError) as error:
                return JsonResponse({'success': False, 'error': str(error)}, status=400)
            except (Student.DoesNotExist, Schedule.DoesNotExist, AttendanceSession.DoesNotExist,
                    Subject.DoesNotExist, ClassRoom.DoesNotExist):
                return JsonResponse({'success': False, 'error': 'Không tìm thấy dữ liệu yêu cầu.'}, status=404)
            except IntegrityError:
                return JsonResponse({'success': False, 'error': 'Mã đã tồn tại hoặc dữ liệu đang được sử dụng.'}, status=409)
            except Exception:
                logger.exception('API failure: %s', request.path)
                return JsonResponse({'success': False, 'error': 'Không thể xử lý yêu cầu. Vui lòng thử lại.'}, status=500)
        return wrapped
    return decorate


def payload(request):
    import json
    try:
        data = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        raise ValueError('Nội dung JSON không hợp lệ.')
    if not isinstance(data, dict):
        raise ValueError('Yêu cầu phải là một đối tượng JSON.')
    return data


def decode_image(value):
    if not isinstance(value, str) or len(value) > 12_000_000:
        raise ValueError('Ảnh không hợp lệ hoặc vượt giới hạn 8 MB.')
    try:
        raw = base64.b64decode(value.split(',', 1)[-1], validate=True)
        if len(raw) > 8_000_000 or not raw:
            raise ValueError()
        frame = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    except Exception:
        raise ValueError('Không đọc được ảnh. Vui lòng chọn ảnh JPG hoặc PNG.')
    if frame is None or frame.shape[0] * frame.shape[1] > 25_000_000:
        raise ValueError('Ảnh không hợp lệ hoặc quá lớn.')
    if max(frame.shape[:2]) > 1600:
        ratio = 1600 / max(frame.shape[:2])
        frame = cv2.resize(frame, (0, 0), fx=ratio, fy=ratio)
    return frame


def student_fields(data, student=None):
    code = str(data.get('student_id', student.student_id if student else '')).strip()
    name = str(data.get('full_name', data.get('name', student.full_name if student else ''))).strip()
    class_name = str(data.get('class_name', student.class_name if student else '')).strip()
    email = str(data.get('email', student.email if student else '')).strip()
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,20}', code):
        raise ValueError('Mã sinh viên dài tối đa 20 ký tự, chỉ gồm chữ, số, gạch ngang và gạch dưới.')
    fr.person_directory(code)
    if not name or len(name) > 100 or len(class_name) > 50:
        raise ValueError('Vui lòng nhập họ tên hợp lệ (tối đa 100 ký tự).')
    if email:
        validate_email(email)
    duplicate = Student.objects.filter(student_id=code)
    if student:
        duplicate = duplicate.exclude(pk=student.pk)
    if duplicate.exists():
        raise ValueError('Mã sinh viên đã tồn tại.')
    return {'student_id': code, 'full_name': name, 'class_name': class_name, 'email': email}


def student_json(student):
    return {'id': student.pk, 'student_id': student.student_id, 'full_name': student.full_name,
            'class_name': student.class_name, 'email': student.email, 'is_registered': student.is_registered}


def sync_class(student):
    # class_name is the selected primary class. Keep membership aligned after edits.
    student.classrooms.clear()
    if student.class_name:
        classroom, _ = ClassRoom.objects.get_or_create(
            class_id=student.class_name, defaults={'name': student.class_name})
        classroom.students.add(student)


def stats():
    today = timezone.localdate()
    total = Student.objects.count()
    records = AttendanceRecord.objects.filter(date=today)
    present = records.filter(status__in=['present', 'late']).values('student_id').distinct().count()
    registered = Student.objects.filter(is_registered=True).count()
    return {'total_students': total, 'registered_students': registered,
            'today_present': present, 'today_absent': max(0, total - present),
            'attendance_rate': round(present * 100 / total, 1) if total else 0,
            'active_cameras': Camera.objects.filter(status='active').count(),
            'today_sessions': AttendanceSession.objects.filter(date=today).count(),
            'active_sessions': AttendanceSession.objects.filter(status='active', date=today).count(),
            'avg_scan_time': round(fr.last_scan_ms / 1000, 3) if fr.last_scan_ms is not None else None,
            'last_sync': timezone.localtime().strftime('%H:%M:%S')}


def page(request, template, active, **context):
    context.update({'active_nav': active, 'today': timezone.localdate(), 'stats': stats()})
    return render(request, template, context)


def home(request):
    return page(request, 'portal/home.html', 'home',
                recent_records=AttendanceRecord.objects.select_related('student', 'session')[:6],
                today_schedules=Schedule.objects.filter(is_active=True, day_of_week=timezone.localdate().weekday())
                .select_related('subject', 'classroom')[:4])


def admin_dashboard(request):
    return page(request, 'portal/admin_dashboard.html', 'admin', students=Student.objects.all(),
                recent_records=AttendanceRecord.objects.select_related('student', 'session')[:200],
                cameras=Camera.objects.all())


def register_face(request):
    return page(request, 'portal/register.html', 'register', classrooms=ClassRoom.objects.all())


def scan_camera(request):
    return page(request, 'portal/scan_camera.html', 'scan', students=Student.objects.filter(is_registered=True))


def technology(request):
    return page(request, 'portal/technology.html', 'technology')


def schedule_view(request):
    schedules = Schedule.objects.filter(is_active=True).select_related('subject', 'classroom')
    today = timezone.localdate()
    return page(request, 'portal/schedule.html', 'schedule',
                schedule_by_day={day: {'name': name, 'schedules': schedules.filter(day_of_week=day)}
                                 for day, name in Schedule.DAY_CHOICES},
                current_day=today.weekday(), subjects=Subject.objects.all(), classrooms=ClassRoom.objects.all(),
                today_sessions=AttendanceSession.objects.filter(date=today).select_related('schedule__subject', 'schedule__classroom'),
                active_sessions=AttendanceSession.objects.filter(date=today, status='active').select_related('schedule__subject', 'schedule__classroom'))


def activate_session(schedule, date):
    if date != timezone.localdate():
        raise ValueError('Chỉ mở điểm danh cho ngày hôm nay.')
    if schedule.day_of_week != date.weekday():
        raise ValueError('Lịch học này không diễn ra vào hôm nay.')
    if not schedule.is_active:
        raise ValueError('Lịch học này đã ngừng hoạt động.')
    session, created = AttendanceSession.objects.get_or_create(
        schedule=schedule, date=date, defaults={'status': 'active', 'start_time': timezone.now()})
    if not created:
        if session.status in ('completed', 'cancelled'):
            raise ValueError('Buổi học đã đóng. Vui lòng xem lại kết quả.')
        if session.status == 'scheduled':
            session.status = 'active'
            session.start_time = timezone.now()
            session.save()
    return session, created


@require_http_methods(['POST'])
def start_attendance_session(request, schedule_id):
    schedule = get_object_or_404(Schedule, pk=schedule_id)
    try:
        session, _ = activate_session(schedule, timezone.localdate())
    except ValueError:
        session = AttendanceSession.objects.filter(schedule=schedule, date=timezone.localdate()).first()
        return redirect('portal:attendance_session', session_id=session.pk) if session else redirect('portal:schedule')
    return redirect('portal:attendance_session', session_id=session.pk)


def attendance_session(request, session_id):
    session = get_object_or_404(AttendanceSession.objects.select_related('schedule__subject', 'schedule__classroom'), pk=session_id)
    return page(request, 'portal/attendance_session.html', 'schedule', session=session,
                students_in_class=session.schedule.classroom.students.all(), attendance_records=session.session_records.select_related('student'),
                attended_count=session.get_present_count(), total_students=session.get_total_students())


@require_http_methods(['POST'])
def end_attendance_session(request, session_id):
    session = get_object_or_404(AttendanceSession, pk=session_id)
    with transaction.atomic():
        if session.status == 'active':
            seen = session.session_records.values_list('student_id', flat=True)
            for student in session.schedule.classroom.students.exclude(pk__in=seen):
                AttendanceRecord.objects.get_or_create(session=session, student=student, date=session.date,
                                                       defaults={'status': 'absent'})
            session.status = 'completed'
            session.end_time = timezone.now()
            session.save()
    return redirect('portal:attendance_session', session_id=session.pk)


def gen_frames(camera):
    try:
        while True:
            frame = camera.get_frame()
            if frame is None:
                break
            yield b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame + b'\r\n'
    finally:
        camera.close()


def stream(session=None):
    camera = fr.VideoCamera(session_id=session.pk if session else None)
    if not camera.video.isOpened():
        camera.close()
        return JsonResponse({'success': False, 'error': 'Không mở được camera trên máy chủ.'}, status=503)
    return StreamingHttpResponse(gen_frames(camera), content_type='multipart/x-mixed-replace; boundary=frame')


@require_http_methods(['GET'])
def video_feed(request):
    return stream()


@require_http_methods(['GET'])
def video_feed_session(request, session_id):
    session = get_object_or_404(AttendanceSession, pk=session_id)
    if session.status != 'active' or session.date != timezone.localdate():
        return JsonResponse({'success': False, 'error': 'Buổi điểm danh không hoạt động.'}, status=409)
    return stream(session)


@api(['GET'])
def api_stats(request):
    return JsonResponse({'success': True, 'data': stats()})


def record_json(record, created=False):
    return {'student_id': record.student.student_id, 'student_name': record.student.full_name,
            'class_name': record.student.class_name, 'time_in': record.time_in.strftime('%H:%M:%S') if record.time_in else None,
            'time': record.time_in.strftime('%H:%M:%S') if record.time_in else None,
            'date': str(record.date), 'status': record.status, 'confidence': record.confidence,
            'session_id': record.session_id, 'created': created}


@api(['POST'])
def api_record_attendance(request):
    data = payload(request)
    student = Student.objects.get(student_id=data.get('student_id'))
    record, created = record_student(student, data.get('confidence', 0), camera_id=str(data.get('camera_id', ''))[:50])
    return JsonResponse({'success': True, 'message': 'Đã ghi nhận điểm danh.', 'data': record_json(record, created)})


@api(['GET'])
def api_students(request):
    return JsonResponse({'success': True, 'data': [student_json(s) for s in Student.objects.all()]})


@api(['GET'])
def api_attendance_today(request):
    records = AttendanceRecord.objects.filter(date=timezone.localdate()).select_related('student')
    return JsonResponse({'success': True, 'date': str(timezone.localdate()), 'data': [record_json(r) for r in records]})


@api(['POST'])
def api_register_face(request):
    data = payload(request)
    # Existing IDs may receive more samples, but cannot be silently reassigned to a new person.
    existing = Student.objects.filter(student_id=str(data.get('student_id', '')).strip()).first()
    fields = student_fields(data, existing)
    if existing and existing.full_name != fields['full_name']:
        raise ValueError('Mã sinh viên đã thuộc một hồ sơ khác. Hãy chỉnh sửa hồ sơ trước.')
    images = data.get('images')
    if not isinstance(images, list) or not 1 <= len(images) <= 12:
        raise ValueError('Vui lòng chọn từ 1 đến 12 ảnh.')
    frames = [decode_image(image) for image in images]
    samples = fr.extract_registration(frames)
    with transaction.atomic():
        student, created = Student.objects.update_or_create(student_id=fields['student_id'],
                                                           defaults={**fields, 'is_registered': True})
        count = fr.store_registration(student.student_id, samples)
        sync_class(student)
    return JsonResponse({'success': True, 'message': f'Đã lưu {count}/{len(images)} ảnh hợp lệ.',
                         'data': {**student_json(student), 'faces_registered': count, 'created': created}})


@api(['PUT'])
def api_update_student(request, student_id):
    data = payload(request)
    student = Student.objects.get(pk=student_id)
    fields = student_fields(data, student)
    old_code = student.student_id
    with fr._database_lock:
        database = fr.load_database()
        if fields['student_id'] != old_code:
            old_dir = fr.person_directory(old_code)
            new_dir = fr.person_directory(fields['student_id'])
            if new_dir.exists() or fields['student_id'] in database:
                raise ValueError('Mã mới đã có dữ liệu khuôn mặt.')
            if old_dir.exists():
                old_dir.rename(new_dir)
            if old_code in database:
                database[fields['student_id']] = database.pop(old_code)
        # Legacy keys are migrated to student ID, preserving name changes and duplicate names.
        if Student.objects.filter(full_name__iexact=student.full_name).count() == 1:
            for legacy in [key for key in database if key.casefold() == student.full_name.casefold()
                           and key != fields['student_id'] and student_for_identity(key) == student]:
                database.setdefault(fields['student_id'], []).extend(database.pop(legacy))
        fr.save_database(database)
    for key, value in fields.items():
        setattr(student, key, value)
    student.save()
    sync_class(student)
    return JsonResponse({'success': True, 'message': 'Đã cập nhật hồ sơ.', 'data': student_json(student)})


@api(['DELETE'])
def api_delete_student(request, student_id):
    student = Student.objects.get(pk=student_id)
    keys = [student.student_id]
    with fr._database_lock:
        database = fr.load_database()
        if student_for_identity(student.full_name) == student:
            keys.append(student.full_name)
            keys.extend(name for name in database if name.casefold() == student.full_name.casefold()
                        and student_for_identity(name) == student and name not in keys)
        for key in keys:
            database.pop(key, None)
            try:
                folder = fr.person_directory(key)
            except ValueError:
                continue
            if folder.exists():
                shutil.rmtree(folder)
        fr.save_database(database)
    student.delete()
    return JsonResponse({'success': True, 'message': 'Đã xóa hồ sơ và dữ liệu khuôn mặt liên quan.'})


@api(['POST'])
def api_recognize_face(request):
    data = payload(request)
    frame = decode_image(data.get('image'))
    session = None
    if data.get('session_id'):
        session = AttendanceSession.objects.get(pk=data['session_id'])
        if session.status != 'active' or session.date != timezone.localdate():
            raise ValueError('Buổi điểm danh không hoạt động trong ngày hôm nay.')
    results = fr.recognize_frame(frame)
    recognized = []
    for result in results:
        result = dict(result)
        identity = result['name']
        student = student_for_identity(identity) if identity != 'Unknown' else None
        result.update({'student_id': student.student_id if student else None,
                       'name': student.full_name if student else 'Chưa xác định', 'recorded': False})
        if student and data.get('record', True):
            try:
                record, created = record_student(student, result['confidence'], session=session, camera_id='BROWSER')
                result.update({'recorded': True, 'created': created, 'time_in': record_json(record)['time_in']})
            except ValueError as error:
                result['reason'] = str(error)
        recognized.append(result)
    return JsonResponse({'success': True, 'data': {'faces_detected': len(results), 'recognized': recognized,
                                                  'image_width': frame.shape[1], 'image_height': frame.shape[0],
                                                  'scan_ms': fr.last_scan_ms, 'threshold': round(fr.THRESHOLD * 100, 2)}})


@api(['GET'])
def api_registered_faces(request):
    database = fr.load_database()
    data = []
    for identity, embeddings in database.items():
        student = student_for_identity(identity)
        data.append({'identity': identity, 'name': student.full_name if student else identity,
                     'student_id': student.student_id if student else None, 'embeddings_count': len(embeddings)})
    return JsonResponse({'success': True, 'data': data})


@api(['GET', 'POST'])
def api_schedules(request):
    if request.method == 'POST':
        data = payload(request)
        day, start, end = int(data.get('day_of_week', -1)), int(data.get('start_period', 0)), int(data.get('end_period', 0))
        if not 0 <= day <= 6 or not 1 <= start <= end <= 10:
            raise ValueError('Thứ hoặc khoảng tiết học không hợp lệ.')
        subject_name = str(data.get('subject_name', '')).strip()
        subject_code = str(data.get('subject_code', '')).strip()
        class_id = str(data.get('class_id', '')).strip()
        if not subject_name or not subject_code or not class_id or len(subject_name) > 100 or max(len(subject_code), len(class_id)) > 20:
            raise ValueError('Vui lòng nhập mã môn, tên môn và mã lớp hợp lệ.')
        room = str(data.get('room', '')).strip()
        if len(room) > 50:
            raise ValueError('Tên phòng tối đa 50 ký tự.')
        with transaction.atomic():
            subject, _ = Subject.objects.get_or_create(code=subject_code, defaults={'name': subject_name})
            classroom, _ = ClassRoom.objects.get_or_create(class_id=class_id, defaults={'name': class_id})
            if Schedule.objects.filter(classroom=classroom, day_of_week=day, is_active=True,
                                       start_period__lte=end, end_period__gte=start).exists():
                raise ValueError('Lớp này đã có lịch học trùng tiết.')
            schedule = Schedule.objects.create(subject=subject, classroom=classroom, day_of_week=day,
                                               start_period=start, end_period=end, room=room)
            classroom.students.add(*Student.objects.filter(class_name=class_id))
        return JsonResponse({'success': True, 'message': 'Đã thêm lịch học.', 'data': {'id': schedule.pk}}, status=201)
    schedules = Schedule.objects.filter(is_active=True).select_related('subject', 'classroom')
    if request.GET.get('day') is not None:
        day = int(request.GET['day'])
        if not 0 <= day <= 6:
            raise ValueError('Thứ không hợp lệ.')
        schedules = schedules.filter(day_of_week=day)
    return JsonResponse({'success': True, 'data': [
        {'id': s.pk, 'subject': s.subject.name, 'subject_code': s.subject.code,
         'classroom': s.classroom.name, 'class_id': s.classroom.class_id, 'day_of_week': s.day_of_week,
         'day_name': s.get_day_of_week_display(), 'start_period': s.start_period, 'end_period': s.end_period,
         'time_range': s.get_time_range(), 'room': s.room} for s in schedules]})


@api(['GET'])
def api_sessions_today(request):
    sessions = AttendanceSession.objects.filter(date=timezone.localdate()).select_related('schedule__subject', 'schedule__classroom')
    return JsonResponse({'success': True, 'data': [
        {'id': s.pk, 'subject': s.schedule.subject.name, 'classroom': s.schedule.classroom.name,
         'date': str(s.date), 'status': s.status, 'status_display': s.get_status_display(),
         'present_count': s.get_present_count(), 'total_students': s.get_total_students(),
         'start_time': timezone.localtime(s.start_time).strftime('%H:%M:%S') if s.start_time else None} for s in sessions]})


@api(['GET'])
def api_session_attendance(request, session_id):
    session = AttendanceSession.objects.get(pk=session_id)
    return JsonResponse({'success': True, 'session': {'id': session.pk, 'status': session.status,
                         'total_students': session.get_total_students(), 'present_count': session.get_present_count(),
                         'date': str(session.date), 'subject': session.schedule.subject.name, 'classroom': session.schedule.classroom.name},
                         'data': [record_json(r) for r in session.session_records.select_related('student')]})


@api(['POST'])
def api_record_session_attendance(request):
    data = payload(request)
    session = AttendanceSession.objects.get(pk=data.get('session_id'))
    student = (Student.objects.get(student_id=data['student_id']) if data.get('student_id')
               else student_for_identity(data.get('student_name', '')))
    if not student:
        raise Student.DoesNotExist()
    record, created = record_student(student, data.get('confidence', 0), session=session)
    return JsonResponse({'success': True, 'data': record_json(record, created), 'message': 'Đã điểm danh buổi học.'})


@api(['POST'])
def api_create_session(request):
    data = payload(request)
    schedule = Schedule.objects.get(pk=data.get('schedule_id'))
    date = datetime.date.fromisoformat(data['date']) if data.get('date') else timezone.localdate()
    session, created = activate_session(schedule, date)
    return JsonResponse({'success': True, 'data': {'session_id': session.pk, 'created': created,
                         'subject': schedule.subject.name, 'classroom': schedule.classroom.name, 'date': str(date)}})


@api(['GET'])
def api_system(request):
    import onnxruntime as ort
    providers = []
    if fr._face_app is not None:
        providers = fr._face_app.models['recognition'].session.get_providers()
    return JsonResponse({'success': True, 'data': {
        'opencv': cv2.__version__, 'engine': 'InsightFace', 'model': fr.MODEL_NAME,
        'threshold': round(fr.THRESHOLD * 100, 2), 'model_loaded': fr._face_app is not None,
        'available_providers': ort.get_available_providers(), 'active_providers': providers,
        'database': settings.DATABASES['default']['ENGINE'].split('.')[-1], 'scan_ms': fr.last_scan_ms}})


@api(['GET'])
def export_attendance(request):
    records = AttendanceRecord.objects.select_related('student', 'session__schedule__subject')
    if request.GET.get('session'):
        records = records.filter(session_id=int(request.GET['session']))
    else:
        date = datetime.date.fromisoformat(request.GET.get('date', str(timezone.localdate())))
        records = records.filter(date=date)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(['Mã sinh viên', 'Họ tên', 'Lớp', 'Ngày', 'Giờ vào', 'Trạng thái', 'Điểm tương đồng (%)', 'Buổi'])
    def cell(value):
        value = str(value)
        return "'" + value if value.startswith(('=', '+', '-', '@')) else value
    for record in records:
        writer.writerow([cell(record.student.student_id), cell(record.student.full_name), cell(record.student.class_name),
                         record.date, record.time_in or '', record.get_status_display(), record.confidence,
                         record.session_id or 'Tự do'])
    response = HttpResponse('\ufeff' + buffer.getvalue(), content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="attendance.csv"'
    return response

