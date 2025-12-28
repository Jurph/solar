from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from mysite.universe.models.celestial import Galaxy


class TestUniverseViews(TestCase):
    def test_universe_view_renders(self):
        url = reverse("universe")
        resp = self.client.get(url)
        assert resp.status_code == 200

    def test_object_details_invalid_type(self):
        url = reverse("object_details", kwargs={"object_type": "not-a-type", "object_id": 1})
        resp = self.client.get(url)
        assert resp.status_code == 400
        assert resp.json()["error"] == "Invalid object type"

    def test_object_details_galaxy_success(self):
        galaxy = Galaxy.objects.create(name="Test Galaxy", galaxy_type="SP", galaxy_size="L")
        url = reverse("object_details", kwargs={"object_type": "galaxy", "object_id": galaxy.id})
        resp = self.client.get(url)
        assert resp.status_code == 200
        data = resp.json()
        # We don't over-specify serializer output; just ensure key identity fields exist.
        assert data.get("name") == "Test Galaxy"

    def test_object_details_returns_500_when_serializer_throws(self):
        galaxy = Galaxy.objects.create(name="Broken Galaxy", galaxy_type="SP", galaxy_size="L")
        url = reverse("object_details", kwargs={"object_type": "galaxy", "object_id": galaxy.id})

        with patch("mysite.universe.views.universe.get_serializer_for_instance", side_effect=RuntimeError("boom")):
            resp = self.client.get(url)

        assert resp.status_code == 500
        assert "boom" in resp.json()["error"]


