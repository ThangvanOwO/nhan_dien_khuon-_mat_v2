from django.contrib import admin
from .models import Student, AttendanceRecord, Camera, SystemStats


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['student_id', 'full_name', 'class_name', 'is_registered', 'created_at']
    list_filter = ['is_registered', 'class_name', 'created_at']
    search_fields = ['student_id', 'full_name', 'email']
    ordering = ['student_id']


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ['student', 'date', 'time_in', 'status', 'confidence']
    list_filter = ['status', 'date', 'camera_id']
    search_fields = ['student__student_id', 'student__full_name']
    date_hierarchy = 'date'
    ordering = ['-date', '-time_in']


@admin.register(Camera)
class CameraAdmin(admin.ModelAdmin):
    list_display = ['camera_id', 'name', 'location', 'status', 'last_active']
    list_filter = ['status']
    search_fields = ['camera_id', 'name', 'location']


@admin.register(SystemStats)
class SystemStatsAdmin(admin.ModelAdmin):
    list_display = ['date', 'total_students', 'attendance_rate', 'total_scans']
    date_hierarchy = 'date'
    ordering = ['-date']
