from __future__ import annotations

import logging
from unittest.mock import patch

from django.test import TestCase

from mysite.universe.models.actor import Satellite
from mysite.universe.models.event import DialogueEvent, DialogueEventLog
from mysite.universe.signals import dialogue_event_processed

# Import receivers module so the signal receiver is registered.
from mysite.universe import receivers as receivers_module  # noqa: F401


class TestDialogueEventReceiver(TestCase):
    def setUp(self):
        self.satellite = Satellite.objects.create(name="Test Sat")

    def _call_receiver(self, text: str):
        event = DialogueEvent(timestamp=1.25, actor=self.satellite, text=text, duration=1.0, metadata={})

        # Avoid writing dialogue_event_debug.log during tests.
        with patch.object(logging.getLogger("dialogue_event_debug"), "handlers", [logging.NullHandler()]):
            dialogue_event_processed.send(sender=self.__class__, event=event)

    def test_receiver_saves_plain_text(self):
        self._call_receiver("Hello world")
        log = DialogueEventLog.objects.get()
        assert log.actor_name == self.satellite.name
        assert log.text == "Hello world"
        assert log.timestamp == 1.25

    def test_receiver_extracts_message_from_json_object(self):
        self._call_receiver('{"message": "HELLO FROM JSON"}')
        log = DialogueEventLog.objects.get()
        assert log.text == "HELLO FROM JSON"

    def test_receiver_extracts_message_from_embedded_json(self):
        self._call_receiver('prefix {"message": "HI\\\\nTHERE"} suffix')
        log = DialogueEventLog.objects.get()
        assert log.text == "HI\\nTHERE"

    def test_receiver_regex_extracts_message_on_json_decode_error(self):
        # Valid braces but invalid JSON (trailing comma) => JSONDecodeError => regex fallback.
        self._call_receiver('{ "message": "HELLO VIA REGEX", }')
        log = DialogueEventLog.objects.get()
        assert log.text == "HELLO VIA REGEX"

    def test_receiver_does_not_write_debug_log_file(self):
        # Cover the branch that would normally create a FileHandler, but patch it to a NullHandler.
        event = DialogueEvent(timestamp=3.0, actor=self.satellite, text="Hello", duration=1.0, metadata={})
        debug_logger = logging.getLogger("dialogue_event_debug")

        with (
            patch.object(debug_logger, "handlers", []),
            patch("logging.FileHandler", return_value=logging.NullHandler()),
        ):
            receivers_module.save_dialogue_event_to_db(sender=self.__class__, event=event)
        assert DialogueEventLog.objects.count() == 1

    def test_receiver_keeps_json_text_when_no_message_field_present(self):
        self._call_receiver("{}")
        log = DialogueEventLog.objects.get()
        assert log.text == "{}"

    def test_receiver_fallbacks_when_json_parse_fails_and_no_message_found(self):
        self._call_receiver("{not valid json")
        log = DialogueEventLog.objects.get()
        assert log.text == "[Error: Could not extract dialogue message]"

    def test_receiver_does_not_raise_if_db_save_fails(self):
        event = DialogueEvent(timestamp=2.0, actor=self.satellite, text="Hello", duration=1.0, metadata={})
        with (
            patch.object(logging.getLogger("dialogue_event_debug"), "handlers", [logging.NullHandler()]),
            patch.object(DialogueEventLog.objects, "create", side_effect=RuntimeError("DB down")),
        ):
            # Should swallow exceptions and only log
            receivers_module.save_dialogue_event_to_db(sender=self.__class__, event=event)

