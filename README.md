# 🚀 Hệ Thống Chấm Công Nhận Diện Khuôn Mặt (GPU Optimized)

Dự án sử dụng Python và thư viện **InsightFace** để nhận diện khuôn mặt thời gian thực. Hệ thống đã được tối ưu hóa để chạy trên **NVIDIA GPU (RTX 3050)** thông qua CUDA, đạt tốc độ xử lý cao (30-60 FPS) thay vì chỉ 1 FPS khi chạy bằng CPU.

## 🛠 Yêu cầu phần cứng & Phần mềm

* **OS:** Windows 10/11
* **CPU:** Intel Core i7 (hoặc tương đương)
* **GPU:** NVIDIA RTX 3000 series trở lên (Đã test trên RTX 3050 Laptop).
* **Python:** 3.10 - 3.12 (Khuyên dùng 3.12).
* **Editor:** VS Code.

---

## ⚙️ Hướng dẫn cài đặt môi trường (Quan trọng)

Đây là phần khó nhất do xung đột phiên bản. Hãy làm chính xác từng bước.

### Bước 1: Cài đặt thư viện Python

Mở Terminal trong VS Code và chạy lệnh sau để gỡ bản cũ (CPU) và cài bản mới (GPU):

```bash
pip uninstall onnxruntime onnxruntime-gpu insightface -y
pip install numpy opencv-python insightface onnxruntime-gpu
```

### Bước 2: Cài đặt NVIDIA CUDA Toolkit 12.4

> ⚠️ **Lưu ý:** Dù `nvidia-smi` có hiện CUDA 13.x thì bắt buộc phải cài CUDA 12.4 để tương thích với thư viện Python.

1. Tải [CUDA Toolkit 12.4 (bản Archive)](https://developer.nvidia.com/cuda-12-4-0-download-archive).

2. Chạy file cài đặt `.exe`.

3. Chọn chế độ **Custom (Advanced)** (Tuyệt đối không chọn Express).

4. Tại danh sách cài đặt:
   - ❌ **BỎ TÍCH:** Driver components (Để tránh lỗi Installer Failed do driver máy mới hơn driver bộ cài).
   - ❌ **BỎ TÍCH:** Visual Studio Integration (Để tránh lỗi Not Installed).
   - ✅ **CHỈ TÍCH:** CUDA (Runtime, Development...).

5. Tiến hành cài đặt (Next -> Finish).

### Bước 3: Cài đặt NVIDIA cuDNN 9 (Động cơ AI)

Thư viện `onnxruntime-gpu` mới nhất yêu cầu cuDNN 9.

1. Tải [cuDNN 9.x for CUDA 12 (File Zip)](https://developer.nvidia.com/cudnn) từ trang chủ NVIDIA.

2. Giải nén file, bạn sẽ thấy 3 thư mục: `bin`, `include`, `lib`.

3. Copy toàn bộ 3 thư mục đó.

4. Dán đè (Paste & Replace) vào đường dẫn cài đặt CUDA:

```
C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.4
```

---

## 📁 Cấu trúc thư mục

```
DepartureByLiru/
├── project.py          # File chính chạy chương trình
├── my_faces/           # Thư mục chứa ảnh khuôn mặt đăng ký
│   └── <tên_người>/    # Mỗi người 1 thư mục con
│       └── *.jpg       # Ảnh khuôn mặt
└── README.md           # Hướng dẫn này
```

---

## 🚀 Cách sử dụng

1. Thêm ảnh khuôn mặt vào thư mục `my_faces/<tên_người>/`
2. Chạy chương trình:

```bash
python project.py
```

---

## ✅ Kiểm tra GPU đang hoạt động

Chạy lệnh sau để xác nhận GPU được sử dụng:

```python
import onnxruntime as ort
print(ort.get_available_providers())
# Kết quả mong đợi: ['CUDAExecutionProvider', 'CPUExecutionProvider']
```

Nếu chỉ thấy `CPUExecutionProvider`, kiểm tra lại bước cài đặt CUDA và cuDNN.

---

## 📝 License

MIT License
