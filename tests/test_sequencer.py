"""Тесты мини-секвенсора: ноты, смешивание, WAV и MIDI."""
import io
import os
import struct
import sys
import time
import unittest
import wave

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import sequencer  # noqa: E402


class NoteTests(unittest.TestCase):
    def test_top_row_is_the_highest_and_key_shifts_every_note(self):
        notes = [sequencer.melody_note(row, 0, "minor_pentatonic") for row in sequencer.MELODY_ROWS]
        self.assertEqual(notes, sorted(notes, reverse=True))
        self.assertEqual(sequencer.melody_note(0, 2, "major"), sequencer.melody_note(0, 0, "major") + 2)


class MixerTests(unittest.TestCase):
    def test_block_length_follows_the_tempo(self):
        fast = sequencer.Mixer(set(), bpm=180).block(0)[0]
        slow = sequencer.Mixer(set(), bpm=60).block(0)[0]
        self.assertAlmostEqual(len(slow) / len(fast), 3, places=1)

    def test_silence_when_muted_or_empty(self):
        self.assertEqual(sequencer.Mixer(set()).block(0)[1], 0.0)
        mixer = sequencer.Mixer({(0, sequencer.KICK)})
        mixer.muted = True
        self.assertEqual(mixer.block(0)[1], 0.0)

    def test_every_timbre_and_drum_sounds(self):
        for timbre in sequencer.TIMBRES:
            self.assertGreater(sequencer.Mixer({(0, 0)}, timbre=timbre).block(0)[1], 0.01, timbre)
        for row in (sequencer.HAT, sequencer.SNARE, sequencer.KICK):
            self.assertGreater(sequencer.Mixer({(0, row)}).block(0)[1], 0.01, row)

    def test_note_tail_rings_into_the_next_step(self):
        mixer = sequencer.Mixer({(0, 0)})
        mixer.block(0)
        self.assertGreater(mixer.block(1)[1], 0.0)


class ExportTests(unittest.TestCase):
    def test_wav_is_one_loop_long(self):
        data = sequencer.wav_bytes({(0, sequencer.KICK)}, 90, 0, "major", "sine")
        with wave.open(io.BytesIO(data)) as wav:
            self.assertEqual(wav.getframerate(), sequencer.SAMPLE_RATE)
            expected = round(sequencer.SAMPLE_RATE * 60 / 90 / 4) * sequencer.STEPS
            self.assertEqual(wav.getnframes(), expected)

    def test_midi_structure_notes_and_channels(self):
        data = sequencer.midi_bytes({(0, 0), (4, sequencer.KICK)}, 120, 0, "major")
        self.assertTrue(data.startswith(b"MThd"))
        self.assertEqual(struct.unpack(">HHH", data[8:14]), (0, 1, 96))
        self.assertIn(b"MTrk", data)
        self.assertIn(bytes((0x90, sequencer.melody_note(0, 0, "major"), 100)), data)
        self.assertIn(bytes((0x99, 36, 100)), data)  # кик на канале 10
        self.assertIn(b"\xff\x51\x03" + (500000).to_bytes(3, "big"), data)  # 120 BPM
        self.assertTrue(data.endswith(b"\xff\x2f\x00"))

    def test_long_times_use_variable_length(self):
        self.assertEqual(sequencer._vlq(0), b"\x00")
        self.assertEqual(sequencer._vlq(200), b"\x81\x48")


class PlayerTests(unittest.TestCase):
    def test_steps_advance_and_stop_is_clean(self):
        mixer = sequencer.Mixer({(s, sequencer.HAT) for s in range(sequencer.STEPS)}, bpm=180, volume=0.0)
        player = sequencer.Player(mixer)
        seen = set()
        end = time.time() + 1.2
        while time.time() < end:
            seen.add(player.position()[0])
            time.sleep(0.01)
        player.stop()
        self.assertFalse(player.thread.is_alive())
        self.assertGreater(len(seen), 3)


if __name__ == "__main__":
    unittest.main()
