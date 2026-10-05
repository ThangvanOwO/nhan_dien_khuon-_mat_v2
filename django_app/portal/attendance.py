"""One attendance path for browser images, API clients and OpenCV streams."""
import math
from threading import RLock

from django.db import transaction
from django.utils import timezone

from .models import AttendanceRecord, Student

record_lock = RLock()


def validate_confidence(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise ValueError('Điểm tương đồng phải là một số từ 0 đến 100.')
    if not math.isfinite(value) or not 0 <= value <= 100:
        raise ValueError('Điểm tương đồng phải nằm trong khoảng 0–100.')
    return round(value, 2)


def student_for_identity(identity):
    student = Student.objects.filter(student_id=identity).first()
    if student:
        return student
    matches = Student.objects.filter(full_name__iexact=identity)
    return matches.first() if matches.count() == 1 else None


def record_student(student, confidence, session=None, camera_id=''):
    confidence = validate_confidence(confidence)
    now = timezone.localtime()
    if session:
        if session.status != 'active':
            raise ValueError('Buổi điểm danh đã kết thúc hoặc chưa bắt đầu.')
        if session.date != now.date():
            raise ValueError('Chỉ có thể điểm danh buổi học trong ngày hôm nay.')
        if not session.schedule.classroom.students.filter(pk=student.pk).exists():
            raise ValueError('Sinh viên không thuộc lớp của buổi học này.')
    with record_lock, transaction.atomic():
        record, created = AttendanceRecord.objects.get_or_create(
            student=student, session=session, date=session.date if session else now.date(),
            defaults={'time_in': now.time().replace(tzinfo=None), 'status': 'present',
                      'confidence': confidence, 'camera_id': camera_id},
        )
        if not created and record.status == 'absent':
            record.status = 'present'
            record.time_in = now.time().replace(tzinfo=None)
            record.confidence = confidence
            record.camera_id = camera_id
            record.save()
        return record, created
