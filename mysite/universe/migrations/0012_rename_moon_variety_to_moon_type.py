# Generated manually for field rename

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("universe", "0011_moon_albedo_moon_axial_tilt_deg_moon_color_palette_and_more"),
    ]

    operations = [
        migrations.RenameField(
            model_name="moon",
            old_name="variety",
            new_name="moon_type",
        ),
    ]

