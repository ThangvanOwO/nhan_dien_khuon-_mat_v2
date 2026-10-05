"""OpenCV capture/preprocessing + InsightFace embeddings + cosine matching.

Similarity is a matching score, not a calibrated probability or measured accuracy.
"""
import os
import pickle
import re
import tempfile
import time
from uuid import uuid4
from pathlib import Path
from threading import RLock

import cv2
import numpy as np

MODEL_NAME = 'buffalo_l'
THRESHOLD = 0.55
BASE_DIR = Path(__file__).resolve().parents[2]
DATABASE_FILE = BASE_DIR / 'face_database.pkl'
MY_FACES_DIR = BASE_DIR / 'my_faces'
_face_app = None
_model_lock = RLock()
_database_lock = RLock()
_inference_lock = RLock()
last_scan_ms = None


def get_face_app():
    global _face_app
    with _model_lock:
        if _face_app is None:
            import onnxruntime as ort
            from insightface.app import FaceAnalysis
            if hasattr(ort, 'preload_dlls'):
                ort.preload_dlls(directory='')
            providers = ['CPUExecutionProvider']
            if 'CUDAExecutionProvider' in ort.get_available_providers():
                providers.insert(0, 'CUDAExecutionProvider')
            app = FaceAnalysis(name=MODEL_NAME, allowed_modules=['detection', 'recognition'], providers=providers)
            app.prepare(ctx_id=0 if providers[0] == 'CUDAExecutionProvider' else -1, det_size=(640, 640))
            _face_app = app
    return _face_app


def load_database():
    with _database_lock:
        if Path(DATABASE_FILE).exists():
            with open(DATABASE_FILE, 'rb') as handle:
                return pickle.load(handle)
        return {}


def save_database(database):
    with _database_lock:
        target = Path(DATABASE_FILE)
        target.parent.mkdir(parents=True, exist_ok=True)
        handle = tempfile.NamedTemporaryFile(dir=target.parent, suffix='.tmp', delete=False)
        try:
            with handle:
                pickle.dump(database, handle)
            os.replace(handle.name, target)
        finally:
            if os.path.exists(handle.name):
                os.unlink(handle.name)


def person_directory(identity):
    reserved = re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', identity, re.IGNORECASE) if identity else None
    if not identity or reserved or identity.endswith(('.', ' ')) or re.search(r'[\\/:*?"<>|\x00-\x1f]', identity):
        raise ValueError('Mã sinh viên hoặc tên dữ liệu khuôn mặt không hợp lệ.')
    root = Path(MY_FACES_DIR).resolve()
    path = (root / identity).resolve()
    if path.parent != root:
        raise ValueError('Đường dẫn dữ liệu khuôn mặt không hợp lệ.')
    return path


def extract_registration(images):
    app = get_face_app()
    samples = []
    with _inference_lock:
        for image in images:
            faces = app.get(image)
            if len(faces) == 1:
                samples.append((image, np.asarray(faces[0].embedding, dtype=np.float32)))
    if not samples:
        raise ValueError('Mỗi ảnh cần đúng một khuôn mặt rõ nét. Chưa tìm thấy ảnh hợp lệ.')
    return samples


def store_registration(identity, samples):
    person_dir = person_directory(identity)
    with _database_lock:
        database = load_database()
        embeddings = list(database.get(identity, []))
        person_dir.mkdir(parents=True, exist_ok=True)
        for image, embedding in samples:
            filename = person_dir / f'{uuid4().hex}.jpg'
            if not cv2.imwrite(str(filename), image):
                raise OSError('Không thể lưu ảnh khuôn mặt.')
            embeddings.append(embedding)
        database[identity] = embeddings
        save_database(database)
    return len(samples)


def register_face(name, image):
    try:
        store_registration(name, extract_registration([image]))
        return True, 'Đã lưu khuôn mặt.'
    except ValueError as error:
        return False, str(error)


def recognize_face(image):
    global last_scan_ms
    started = time.perf_counter()
    database = load_database()
    app = get_face_app()
    with _inference_lock:
        faces = app.get(image)
    results = []
    for face in faces:
        current = np.asarray(face.embedding)
        best_name, best_score = 'Unknown', 0.0
        for identity, embeddings in database.items():
            for embedding in embeddings:
                embedding = np.asarray(embedding)
                if embedding.shape != current.shape:
                    continue
                denominator = np.linalg.norm(current) * np.linalg.norm(embedding)
                if denominator <= 0:
                    continue
                score = float(np.dot(current, embedding) / denominator)
                if score > best_score:
                    best_score, best_name = score, identity
        results.append({'name': best_name if best_score >= THRESHOLD else 'Unknown',
                        'confidence': round(max(0, min(1, best_score)) * 100, 2),
                        'bbox': face.bbox.astype(int).tolist()})
    last_scan_ms = round((time.perf_counter() - started) * 1000, 1)
    return results


def recognize_frame(frame, scale=1.0):
    if scale <= 0 or scale > 1:
        raise ValueError('Tỷ lệ xử lý ảnh không hợp lệ.')
    image = cv2.resize(frame, (0, 0), fx=scale, fy=scale) if scale != 1 else frame
    results = recognize_face(image)
    if scale != 1:
        for result in results:
            result['bbox'] = (np.asarray(result['bbox']) / scale).astype(int).tolist()
    return results


def draw_results(frame, results):
    for result in results:
        x1, y1, x2, y2 = result['bbox']
        color = (95, 210, 130) if result['name'] != 'Unknown' else (70, 150, 240)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        cv2.putText(frame, f"{result['name']} {result['confidence']:.0f}%", (x1, max(y1 - 8, 20)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    return frame


def record_attendance_to_db(name, confidence, session_id=None):
    from .attendance import record_student, student_for_identity
    from .models import AttendanceSession
    student = student_for_identity(name)
    if not student:
        return False
    session = AttendanceSession.objects.filter(pk=session_id).first() if session_id else None
    if session_id and not session:
        return False
    try:
        record_student(student, confidence, session=session)
        return True
    except ValueError:
        return False


class VideoCamera:
    def __init__(self, camera_id=0, session_id=None):
        backend = cv2.CAP_DSHOW if os.name == 'nt' else cv2.CAP_ANY
        self.video = cv2.VideoCapture(camera_id, backend)
        self.video.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.video.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        self.session_id = session_id

    def close(self):
        self.video.release()

    def get_frame(self, recognize=True):
        ret, frame = self.video.read()
        if not ret:
            return None
        if recognize:
            results = recognize_frame(frame)
            for result in results:
                if result['name'] != 'Unknown':
                    record_attendance_to_db(result['name'], result['confidence'], self.session_id)
            frame = draw_results(frame, results)
        ret, jpeg = cv2.imencode('.jpg', frame)
        return jpeg.tobytes() if ret else None
