from django.db import migrations, models
from django.db.models import Count


def merge_duplicates(apps, schema_editor):
    Record = apps.get_model('portal', 'AttendanceRecord')
    groups = Record.objects.values('student_id', 'session_id', 'date').annotate(total=Count('id')).filter(total__gt=1)
    for group in list(groups):
        records = list(Record.objects.filter(
            student_id=group['student_id'], session_id=group['session_id'], date=group['date']
        ).order_by('id'))
        keep = records[0]
        times = [r.time_in for r in records if r.time_in]
        if times:
            keep.time_in = min(times)
        keep.confidence = max(r.confidence for r in records)
        keep.save()
        Record.objects.filter(pk__in=[r.pk for r in records[1:]]).delete()


class Migration(migrations.Migration):
    dependencies = [('portal', '0002_add_schedule_models')]
    operations = [
        migrations.RunPython(merge_duplicates, migrations.RunPython.noop),
        migrations.AddConstraint(model_name='attendancerecord', constraint=models.UniqueConstraint(
            fields=('student', 'date'), condition=models.Q(session__isnull=True), name='unique_daily_attendance')),
        migrations.AddConstraint(model_name='attendancerecord', constraint=models.UniqueConstraint(
            fields=('session', 'student'), condition=models.Q(session__isnull=False), name='unique_session_attendance')),
    ]
