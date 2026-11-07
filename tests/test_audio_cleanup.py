from mirror_moon.audio import Audio


def test_audio_close_clears_sources_schedules_deletion_and_is_idempotent():
    calls = []

    class Sound:
        def stop(self):
            calls.append("stop")

        def setSource(self, url):
            assert url.isEmpty()
            calls.append("clear")

        def deleteLater(self):
            calls.append("delete")

    audio = Audio.__new__(Audio)
    audio.closed = False
    audio.sounds = {"hum": Sound()}
    audio.close()
    audio.close()
    audio.update(1.0)
    audio.events(())
    assert audio.closed and not audio.sounds and calls == ["stop", "clear", "delete"]
