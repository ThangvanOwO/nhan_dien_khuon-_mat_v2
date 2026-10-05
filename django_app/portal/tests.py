import base64
import datetime
import json
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import skipUnless
from unittest.mock import Mock, patch

import cv2
import numpy as np
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import Client, SimpleTestCase, TestCase
from django.utils import timezone

from . import face_recognition as fr
from .attendance import record_student
from .models import AttendanceRecord, AttendanceSession, Camera, ClassRoom, Schedule, Student, Subject
from .views import gen_frames


def image_payload(blank=False):
    image = np.zeros((80, 80, 3), dtype=np.uint8)
    return 'data:image/png;base64,' + base64.b64encode(cv2.imencode('.png', image)[1]).decode()


class WorkspaceTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db_patch = patch.object(fr, 'DATABASE_FILE', Path(self.temp.name) / 'faces.pkl')
        self.dir_patch = patch.object(fr, 'MY_FACES_DIR', Path(self.temp.name) / 'faces')
        self.scan_patch = patch.object(fr, 'last_scan_ms', None)
        self.db_patch.start()
        self.dir_patch.start()
        self.scan_patch.start()
        self.addCleanup(self.db_patch.stop)
        self.addCleanup(self.dir_patch.stop)
        self.addCleanup(self.scan_patch.stop)
        self.student = Student.objects.create(student_id='SV01', full_name='Nguyễn An', class_name='CV01', is_registered=True)
        self.other = Student.objects.create(student_id='SV02', full_name='Trần Bình', class_name='CV01')
        self.outsider = Student.objects.create(student_id='OUT01', full_name='Ngoài lớp')
        self.subject = Subject.objects.create(code='CV', name='Thị giác máy tính')
        self.classroom = ClassRoom.objects.create(class_id='CV01', name='Lớp CV01')
        self.classroom.students.add(self.student, self.other)
        self.schedule = Schedule.objects.create(subject=self.subject, classroom=self.classroom,
                                               day_of_week=timezone.localdate().weekday(), start_period=1, end_period=3)
        self.session = AttendanceSession.objects.create(schedule=self.schedule, date=timezone.localdate(),
                                                       status='active', start_time=timezone.now())

    def post(self, path, data):
        return self.client.post(path, json.dumps(data), content_type='application/json')

    def test_all_pages_render(self):
        paths = ['/', '/register/', '/admin-dashboard/', '/scan/camera/', '/schedule/', '/technology/',
                 f'/session/{self.session.pk}/', '/admin/login/']
        for path in paths:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'VISTA')

    def test_all_read_apis(self):
        for path in ['/api/stats/', '/api/students/', '/api/attendance/today/', '/api/schedules/',
                     '/api/sessions/today/', '/api/registered-faces/', '/api/system/',
                     f'/api/session/{self.session.pk}/attendance/']:
            with self.subTest(path=path):
                self.assertTrue(self.client.get(path).json()['success'])

    def test_zero_stats_are_real_not_placeholder(self):
        AttendanceRecord.objects.all().delete()
        Student.objects.all().delete()
        result = self.client.get('/api/stats/').json()['data']
        self.assertEqual(result['total_students'], 0)
        self.assertEqual(result['attendance_rate'], 0)
        self.assertEqual(result['active_cameras'], 0)
        self.assertIsNone(result['avg_scan_time'])

    def test_stats_counts_unique_students_and_late(self):
        record_student(self.student, 80)
        record_student(self.student, 80, self.session)
        record = record_student(self.other, 80, self.session)[0]
        record.status = 'late'
        record.save()
        data = self.client.get('/api/stats/').json()['data']
        self.assertEqual(data['today_present'], 2)
        self.assertLessEqual(data['attendance_rate'], 100)
        self.assertEqual(self.session.get_present_count(), 2)

    def test_general_attendance_idempotent_preserves_first_time(self):
        result = self.post('/api/record-attendance/', {'student_id': 'SV01', 'confidence': 89}).json()
        repeated = self.post('/api/record-attendance/', {'student_id': 'SV01', 'confidence': 94}).json()
        self.assertTrue(result['data']['created'])
        self.assertFalse(repeated['data']['created'])
        self.assertEqual(result['data']['time'], repeated['data']['time'])
        self.assertEqual(AttendanceRecord.objects.count(), 1)
        self.assertIsNone(AttendanceRecord.objects.first().time_out)

    def test_general_and_session_are_separate(self):
        record_student(self.student, 80, self.session)
        self.assertTrue(self.post('/api/record-attendance/', {'student_id': 'SV01', 'confidence': 87}).json()['data']['created'])
        self.assertEqual(AttendanceRecord.objects.count(), 2)

    def test_local_timezone_used_at_date_boundary(self):
        now = datetime.datetime(2026, 10, 5, 18, 20, 0, tzinfo=datetime.timezone.utc)
        with patch('django.utils.timezone.now', return_value=now):
            result = self.post('/api/record-attendance/', {'student_id': 'SV01', 'confidence': 80}).json()['data']
        self.assertEqual(result['date'], '2026-10-06')
        self.assertEqual(result['time'], '01:20:00')

    def test_invalid_confidence(self):
        for confidence in [-1, 101, 'NaN', 'Infinity', 'abc', None]:
            with self.subTest(confidence=confidence):
                response = self.post('/api/record-attendance/', {'student_id': 'SV01', 'confidence': confidence})
                self.assertEqual(response.status_code, 400)

    def test_missing_student_404(self):
        self.assertEqual(self.post('/api/record-attendance/', {'student_id': 'MISSING'}).status_code, 404)

    def test_malformed_json_and_non_object(self):
        for path in ['/api/register-face/', '/api/recognize-face/', '/api/record-attendance/',
                     '/api/session/record/', '/api/session/create/', '/api/schedules/']:
            for body in ['{oops', '[]']:
                with self.subTest(path=path, body=body):
                    self.assertEqual(self.client.post(path, body, content_type='application/json').status_code, 400)

    def test_mutating_apis_reject_wrong_methods(self):
        for path in ['/api/register-face/', '/api/recognize-face/', '/api/record-attendance/',
                     '/api/session/record/', '/api/session/create/', f'/api/update-student/{self.student.pk}/',
                     f'/api/delete-student/{self.student.pk}/', f'/session/start/{self.schedule.pk}/',
                     f'/session/{self.session.pk}/end/']:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 405)

    def test_csrf_required_and_valid_token_accepted(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post('/api/record-attendance/', json.dumps({'student_id': 'SV01'}), content_type='application/json')
        self.assertEqual(response.status_code, 403)
        client.get('/')
        token = client.cookies['csrftoken'].value
        response = client.post('/api/record-attendance/', json.dumps({'student_id': 'SV01', 'confidence': 80}),
                               content_type='application/json', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200)

    def test_registration_rejects_bad_images_and_path_ids(self):
        for data in [
            {'student_id': '../oops', 'name': 'Name', 'images': [image_payload()]},
            {'student_id': 'NEW01', 'name': '', 'images': [image_payload()]},
            {'student_id': 'NEW01', 'name': 'Name', 'images': []},
            {'student_id': 'NEW01', 'name': 'Name', 'images': ['not base64']},
            {'student_id': 'NEW01', 'name': 'Name', 'email': 'oops', 'images': [image_payload()]},
            {'student_id': 'NEW01', 'name': 'Name', 'images': [image_payload()] * 13},
        ]:
            self.assertEqual(self.post('/api/register-face/', data).status_code, 400)
        self.assertFalse(Student.objects.filter(student_id='NEW01').exists())

    def test_registration_no_face_does_not_create_student_or_samples(self):
        with patch.object(fr, 'get_face_app', return_value=SimpleNamespace(get=lambda image: [])):
            response = self.post('/api/register-face/', {'student_id': 'NEW01', 'name': 'Name', 'images': [image_payload()]})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Student.objects.filter(student_id='NEW01').exists())
        self.assertEqual(fr.load_database(), {})

    def test_multiple_faces_not_silently_registered(self):
        fake = SimpleNamespace(embedding=np.array([1, 0], dtype=np.float32))
        with patch.object(fr, 'get_face_app', return_value=SimpleNamespace(get=lambda image: [fake, fake])):
            self.assertEqual(self.post('/api/register-face/', {'student_id': 'NEW01', 'name': 'Name', 'images': [image_payload()]}).status_code, 400)

    def test_registration_success_saves_images_embeddings_and_class(self):
        fake = SimpleNamespace(embedding=np.array([1, 0], dtype=np.float32))
        with patch.object(fr, 'get_face_app', return_value=SimpleNamespace(get=lambda image: [fake])):
            response = self.post('/api/register-face/', {'student_id': 'NEW01', 'name': 'Name', 'class_name': 'NEWCLASS',
                                                       'images': [image_payload(), image_payload()]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['data']['faces_registered'], 2)
        student = Student.objects.get(student_id='NEW01')
        self.assertTrue(student.is_registered)
        self.assertEqual(student.classrooms.get().class_id, 'NEWCLASS')
        self.assertEqual(len(fr.load_database()['NEW01']), 2)
        self.assertEqual(len(list(fr.person_directory('NEW01').glob('*.jpg'))), 2)

    def test_existing_id_cannot_be_reassigned_during_registration(self):
        response = self.post('/api/register-face/', {'student_id': 'SV01', 'name': 'Another Person', 'images': [image_payload()]})
        self.assertEqual(response.status_code, 400)

    def test_recognition_dict_results_and_percentages(self):
        detection = [{'name': 'SV01', 'confidence': 86.5, 'bbox': [1, 2, 30, 40]}]
        with patch.object(fr, 'recognize_frame', return_value=detection):
            result = self.post('/api/recognize-face/', {'image': image_payload()})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()['data']['image_width'], 80)
        self.assertEqual(result.json()['data']['image_height'], 80)
        face = result.json()['data']['recognized'][0]
        self.assertEqual(face['name'], self.student.full_name)
        self.assertEqual(face['confidence'], 86.5)
        self.assertTrue(face['recorded'])
        self.assertEqual(AttendanceRecord.objects.get().confidence, 86.5)

    def test_recognition_unknown_and_unlinked_faces_not_recorded(self):
        with patch.object(fr, 'recognize_frame', return_value=[
            {'name': 'Unknown', 'confidence': 30, 'bbox': [1, 2, 30, 40]},
            {'name': 'unlinked', 'confidence': 80, 'bbox': [1, 2, 30, 40]}]):
            response = self.post('/api/recognize-face/', {'image': image_payload()})
        self.assertEqual(response.json()['data']['faces_detected'], 2)
        self.assertFalse(AttendanceRecord.objects.exists())

    def test_recognition_dry_run_does_not_record(self):
        with patch.object(fr, 'recognize_frame', return_value=[{'name': 'SV01', 'confidence': 86, 'bbox': [1, 2, 30, 40]}]):
            self.assertEqual(self.post('/api/recognize-face/', {'image': image_payload(), 'record': False}).status_code, 200)
        self.assertFalse(AttendanceRecord.objects.exists())

    def test_recognition_invalid_images(self):
        for image in [None, '', 'xxx', 123, 'data:image/png;base64,AA==']:
            self.assertEqual(self.post('/api/recognize-face/', {'image': image}).status_code, 400)

    def test_session_recognition_checks_class_membership(self):
        with patch.object(fr, 'recognize_frame', return_value=[{'name': 'OUT01', 'confidence': 86, 'bbox': [1, 2, 30, 40]}]):
            result = self.post('/api/recognize-face/', {'image': image_payload(), 'session_id': self.session.pk})
        self.assertEqual(result.status_code, 200)
        self.assertFalse(result.json()['data']['recognized'][0]['recorded'])
        self.assertFalse(AttendanceRecord.objects.exists())

    def test_session_attendance_idempotent(self):
        data = {'session_id': self.session.pk, 'student_id': 'SV01', 'confidence': 88}
        self.assertTrue(self.post('/api/session/record/', data).json()['data']['created'])
        self.assertFalse(self.post('/api/session/record/', data).json()['data']['created'])
        self.assertEqual(self.session.session_records.count(), 1)

    def test_closed_session_rejects_attendance(self):
        self.session.status = 'completed'
        self.session.save()
        self.assertEqual(self.post('/api/session/record/', {'session_id': self.session.pk, 'student_id': 'SV01'}).status_code, 400)
        self.assertEqual(self.post('/api/recognize-face/', {'image': image_payload(), 'session_id': self.session.pk}).status_code, 400)
        self.assertEqual(self.client.get(f'/session/{self.session.pk}/video_feed/').status_code, 409)

    def test_session_end_marks_missing_students_absent(self):
        record_student(self.student, 88, self.session)
        response = self.client.post(f'/session/{self.session.pk}/end/')
        self.assertEqual(response.status_code, 302)
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, 'completed')
        self.assertEqual(self.session.session_records.get(student=self.other).status, 'absent')
        self.assertIsNotNone(self.session.end_time)
        self.assertEqual(self.session.get_present_count(), 1)

    def test_create_session_idempotent_and_closed_not_reopened(self):
        data = {'schedule_id': self.schedule.pk}
        self.assertFalse(self.post('/api/session/create/', data).json()['data']['created'])
        first_start = self.session.start_time
        self.session.refresh_from_db()
        self.assertEqual(self.session.start_time, first_start)
        self.client.post(f'/session/{self.session.pk}/end/')
        self.assertEqual(self.post('/api/session/create/', data).status_code, 400)

    def test_schedule_creation_and_membership(self):
        data = {'subject_code': 'NEW', 'subject_name': 'Môn mới', 'class_id': 'CV01',
                'day_of_week': 6, 'start_period': 5, 'end_period': 7, 'room': 'A01'}
        self.assertEqual(self.post('/api/schedules/', data).status_code, 201)
        self.assertEqual(Schedule.objects.get(subject__code='NEW').classroom.students.count(), 2)

    def test_schedule_overlap_and_bad_filters_rejected(self):
        data = {'subject_code': 'NEW', 'subject_name': 'Môn mới', 'class_id': 'CV01',
                'day_of_week': self.schedule.day_of_week, 'start_period': 2, 'end_period': 3}
        self.assertEqual(self.post('/api/schedules/', data).status_code, 400)
        self.assertFalse(Subject.objects.filter(code='NEW').exists())
        for day in ['abc', '8', '-1']:
            self.assertEqual(self.client.get('/api/schedules/', {'day': day}).status_code, 400)

    def test_session_invalid_date_and_missing_ids(self):
        for data in [{'schedule_id': self.schedule.pk, 'date': 'bad'},
                     {'schedule_id': self.schedule.pk, 'date': '2050-01-01'}]:
            self.assertEqual(self.post('/api/session/create/', data).status_code, 400)
        self.assertEqual(self.post('/api/session/create/', {'schedule_id': 9999}).status_code, 404)
        self.assertEqual(self.client.get('/api/session/9999/attendance/').status_code, 404)

    def test_update_renames_stable_identity_and_changes_class(self):
        fr.save_database({'SV01': [np.array([1, 0]) ]})
        folder = fr.person_directory('SV01')
        folder.mkdir(parents=True)
        (folder / 'sample.jpg').touch()
        data = {'student_id': 'SVNEW', 'full_name': 'Tên mới', 'class_name': 'NEWCLASS', 'email': 'new@example.com'}
        result = self.client.put(f'/api/update-student/{self.student.pk}/', json.dumps(data), content_type='application/json')
        self.assertEqual(result.status_code, 200)
        self.student.refresh_from_db()
        self.assertEqual(self.student.full_name, 'Tên mới')
        self.assertIn('SVNEW', fr.load_database())
        self.assertNotIn('SV01', fr.load_database())
        self.assertTrue(fr.person_directory('SVNEW').exists())
        self.assertEqual(self.student.classrooms.get().class_id, 'NEWCLASS')

    def test_update_duplicate_code_does_not_corrupt_files(self):
        fr.save_database({'SV01': [np.array([1, 0])]})
        response = self.client.put(f'/api/update-student/{self.student.pk}/',
                                   json.dumps({'student_id': 'SV02'}), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('SV01', fr.load_database())

    def test_update_migrates_legacy_identity_case_insensitively(self):
        fr.save_database({'nguyễn an': [np.array([1, 0])]})
        response = self.client.put(f'/api/update-student/{self.student.pk}/',
                                   json.dumps({'full_name': 'Tên mới'}), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(fr.load_database()), ['SV01'])

    def test_session_wrong_weekday_rejected(self):
        self.session.delete()
        self.schedule.day_of_week = (timezone.localdate().weekday() + 1) % 7
        self.schedule.save()
        response = self.post('/api/session/create/', {'schedule_id': self.schedule.pk})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(AttendanceSession.objects.exists())

    def test_reserved_windows_student_id_rejected_before_model_load(self):
        with patch.object(fr, 'get_face_app') as model:
            response = self.post('/api/register-face/', {'student_id': 'CON', 'name': 'Test', 'images': [image_payload()]})
        self.assertEqual(response.status_code, 400)
        model.assert_not_called()

    def test_delete_only_target_identity_and_records(self):
        fr.save_database({'SV01': [np.array([1, 0])], 'OUT01': [np.array([0, 1])]})
        folder = fr.person_directory('SV01')
        folder.mkdir(parents=True)
        record_student(self.student, 87)
        response = self.client.delete(f'/api/delete-student/{self.student.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Student.objects.filter(pk=self.student.pk).exists())
        self.assertFalse(AttendanceRecord.objects.exists())
        self.assertEqual(list(fr.load_database()), ['OUT01'])
        self.assertFalse(folder.exists())

    def test_delete_name_matching_another_student_id_preserves_other_faces(self):
        self.student.full_name = self.other.student_id
        self.student.save()
        fr.save_database({'SV01': [np.array([1, 0])], 'SV02': [np.array([0, 1])]})
        other_folder = fr.person_directory('SV02')
        other_folder.mkdir(parents=True)
        self.assertEqual(self.client.delete(f'/api/delete-student/{self.student.pk}/').status_code, 200)
        self.assertIn('SV02', fr.load_database())
        self.assertTrue(other_folder.exists())

    def test_update_name_matching_another_student_id_does_not_steal_identity(self):
        self.student.full_name = self.other.student_id
        self.student.save()
        fr.save_database({'SV02': [np.array([0, 1])]})
        result = self.client.put(f'/api/update-student/{self.student.pk}/',
                                 json.dumps({'full_name': 'New name'}), content_type='application/json')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(list(fr.load_database()), ['SV02'])

    def test_csv_export_with_filter_and_formula_escaping(self):
        self.student.full_name = '=FORMULA'
        self.student.save()
        record_student(self.student, 87, self.session)
        record_student(self.other, 87)
        response = self.client.get('/api/attendance/export/', {'session': self.session.pk})
        self.assertEqual(response.status_code, 200)
        text = response.content.decode('utf-8-sig')
        self.assertIn("'=FORMULA", text)
        self.assertNotIn('Trần Bình', text)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')

    def test_database_constraints_enforce_uniqueness(self):
        record_student(self.student, 80)
        with self.assertRaises(IntegrityError), transaction.atomic():
            AttendanceRecord.objects.create(student=self.student, date=timezone.localdate(), status='present')
        record_student(self.student, 80, self.session)
        with self.assertRaises(IntegrityError), transaction.atomic():
            AttendanceRecord.objects.create(student=self.student, session=self.session, date=timezone.localdate(), status='present')

    def test_camera_unavailable_returns_503(self):
        fake = Mock()
        fake.video.isOpened.return_value = False
        with patch.object(fr, 'VideoCamera', return_value=fake):
            self.assertEqual(self.client.get('/video_feed/').status_code, 503)
        fake.close.assert_called_once()

    def test_admin_all_models_available(self):
        admin = User.objects.create_superuser('qa', 'qa@example.com', 'TestAdmin_123')
        self.client.force_login(admin)
        for model in ['student', 'attendancerecord', 'camera', 'systemstats', 'subject', 'classroom', 'schedule', 'attendancesession']:
            self.assertEqual(self.client.get('/admin/portal/' + model + '/').status_code, 200)


class VisionUnitTests(SimpleTestCase):
    def test_camera_stream_ends_on_failure_and_releases(self):
        camera = Mock()
        camera.get_frame.side_effect = [b'jpeg', None]
        frames = list(gen_frames(camera))
        self.assertEqual(len(frames), 1)
        self.assertIn(b'jpeg', frames[0])
        camera.close.assert_called_once()

    def test_camera_stream_releases_on_disconnect(self):
        camera = Mock()
        camera.get_frame.return_value = b'jpeg'
        stream = gen_frames(camera)
        next(stream)
        stream.close()
        camera.close.assert_called_once()

    def test_cosine_known_unknown_empty_and_scaling(self):
        face = SimpleNamespace(embedding=np.array([1, 0]), bbox=np.array([2, 3, 12, 13]))
        with patch.object(fr, 'get_face_app', return_value=SimpleNamespace(get=lambda image: [face])), patch.object(fr, 'load_database', return_value={'SV01': [np.array([1, 0])]}):
            result = fr.recognize_frame(np.zeros((50, 50, 3), dtype=np.uint8), scale=.5)[0]
        self.assertEqual(result['name'], 'SV01')
        self.assertEqual(result['confidence'], 100)
        self.assertEqual(result['bbox'], [4, 6, 24, 26])
        with patch.object(fr, 'get_face_app', return_value=SimpleNamespace(get=lambda image: [face])), patch.object(fr, 'load_database', return_value={'OTHER': [np.array([0, 1])]}):
            self.assertEqual(fr.recognize_face(np.zeros((50, 50, 3), dtype=np.uint8))[0]['name'], 'Unknown')

    def test_path_traversal_rejected(self):
        for identity in ['../a', r'..\a', '/absolute', 'C:drive', '.', '..', 'CON', 'LPT1', 'AUX.txt', 'trailing.']:
            with self.assertRaises(ValueError):
                fr.person_directory(identity)


@skipUnless(os.environ.get('RUN_VISION_TESTS') == '1', 'Set RUN_VISION_TESTS=1 for local real model tests.')
class RealVisionTests(TestCase):
    def test_real_registration_recognition_gpu_and_blank_image(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(fr, 'DATABASE_FILE', Path(temporary) / 'faces.pkl'), patch.object(fr, 'MY_FACES_DIR', Path(temporary) / 'photos'):
            sample = Path(__file__).resolve().parents[2] / 'test.jpeg'
            data = base64.b64encode(sample.read_bytes()).decode()
            response = self.client.post('/api/register-face/', json.dumps({
                'student_id': 'REAL01', 'name': 'Vision Test', 'class_name': 'QA', 'images': [data]
            }), content_type='application/json')
            self.assertEqual(response.status_code, 200, response.content)
            response = self.client.post('/api/recognize-face/', json.dumps({'image': data}), content_type='application/json')
            self.assertEqual(response.status_code, 200, response.content)
            faces = response.json()['data']['recognized']
            self.assertEqual(len(faces), 1)
            self.assertEqual(faces[0]['student_id'], 'REAL01')
            self.assertGreater(faces[0]['confidence'], 95)
            self.assertTrue(faces[0]['recorded'])
            self.assertEqual(AttendanceRecord.objects.count(), 1)
            for model in ('detection', 'recognition'):
                self.assertIn('CUDAExecutionProvider', fr._face_app.models[model].session.get_providers())
            blank = self.client.post('/api/recognize-face/', json.dumps({'image': image_payload()}), content_type='application/json')
            self.assertEqual(blank.status_code, 200)
            self.assertEqual(blank.json()['data']['faces_detected'], 0)
