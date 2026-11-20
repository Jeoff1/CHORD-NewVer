"""Chord sheets in ChordPro (``apps/songs/chords.py``): transposing on the
server (decision 0009), capo shapes, Nashville numbers, checking ChordPro,
and converting chords over words. Song text here is public domain (Amazing
Grace, John Newton, 1779) or made up."""

from django.test import SimpleTestCase

from apps.core.music import MAJOR_KEYS, MINOR_KEYS
from apps.songs import chords
from apps.songs.chords import Chord, ChordProError, Key

AMAZING_GRACE = """{title: Amazing Grace}
{subtitle: John Newton}
{start_of_verse: Verse 1}
[G]Amazing [G/B]grace, how [C]sweet the [G]sound
That [G]saved a wretch like [D]me
{end_of_verse}
{soc}
[Em]I once was [C]lost, but [G]now am [D/F#]found
{eoc}
{c: Repeat}
"""

# Written out by hand, not computed: the I, IV, V and vi chords of every
# major key, spelled as charts in that key spell them.
MAJOR_TABLE = {
    "C": ["C", "F", "G", "Am"],
    "Db": ["Db", "Gb", "Ab", "Bbm"],
    "D": ["D", "G", "A", "Bm"],
    "Eb": ["Eb", "Ab", "Bb", "Cm"],
    "E": ["E", "A", "B", "C#m"],
    "F": ["F", "Bb", "C", "Dm"],
    "F#": ["F#", "B", "C#", "D#m"],
    "G": ["G", "C", "D", "Em"],
    "Ab": ["Ab", "Db", "Eb", "Fm"],
    "A": ["A", "D", "E", "F#m"],
    "Bb": ["Bb", "Eb", "F", "Gm"],
    "B": ["B", "E", "F#", "G#m"],
}
# The i, iv, v and VI chords of every minor key.
MINOR_TABLE = {
    "Cm": ["Cm", "Fm", "Gm", "Ab"],
    "C#m": ["C#m", "F#m", "G#m", "A"],
    "Dm": ["Dm", "Gm", "Am", "Bb"],
    "Ebm": ["Ebm", "Abm", "Bbm", "B"],
    "Em": ["Em", "Am", "Bm", "C"],
    "Fm": ["Fm", "Bbm", "Cm", "Db"],
    "F#m": ["F#m", "Bm", "C#m", "D"],
    "Gm": ["Gm", "Cm", "Dm", "Eb"],
    "G#m": ["G#m", "C#m", "D#m", "E"],
    "Am": ["Am", "Dm", "Em", "F"],
    "Bbm": ["Bbm", "Ebm", "Fm", "Gb"],
    "Bm": ["Bm", "Em", "F#m", "G"],
}


def sheet(chord_names):
    return "".join(f"[{name}]la " for name in chord_names) + "\n"


def shown(text, original, target=None, **options):
    rendered = chords.render(
        text,
        Key.parse(original),
        Key.parse(target) if target else None,
        **options,
    )
    return [
        segment.chord
        for block in rendered.blocks
        for line in block.lines
        for segment in line.segments
        if segment.chord
    ]


class KeyTests(SimpleTestCase):
    def test_every_key_name_parses_back(self):
        for name in (*MAJOR_KEYS, *MINOR_KEYS):
            self.assertEqual(Key.parse(name).name, name)

    def test_enharmonic_names_and_errors(self):
        self.assertEqual(Key.parse("Gb"), Key.parse("F#"))
        self.assertEqual(Key.parse("A#m").name, "Bbm")
        for bad in ("", "H", "m", "Xm", "C##"):
            with self.assertRaises(ValueError):
                Key.parse(bad)

    def test_long_names(self):
        self.assertEqual(Key.parse("Am").long_name, "A minor")
        self.assertEqual(Key.parse("F#m").long_name, "F# minor")
        self.assertEqual(Key.parse("Bb").long_name, "Bb major")

    def test_steps_between_keys(self):
        self.assertEqual(Key.parse("G").steps_to(Key.parse("A")), 2)
        self.assertEqual(Key.parse("A").steps_to(Key.parse("G")), 10)


class TranspositionTests(SimpleTestCase):
    def test_every_major_key_from_a_sharp_key_and_from_a_flat_key(self):
        for source in ("G", "Db"):
            for target, expected in MAJOR_TABLE.items():
                with self.subTest(source=source, target=target):
                    self.assertEqual(
                        shown(sheet(MAJOR_TABLE[source]), source, target), expected
                    )

    def test_every_minor_key(self):
        for source in ("Am", "Ebm"):
            for target, expected in MINOR_TABLE.items():
                with self.subTest(source=source, target=target):
                    self.assertEqual(
                        shown(sheet(MINOR_TABLE[source]), source, target), expected
                    )

    def test_sharps_or_flats_follow_the_target_key(self):
        # The same chord (the bVII of G) spelled for the key it is shown in.
        self.assertEqual(shown(sheet(["F", "Bb"]), "G", "A"), ["G", "C"])
        self.assertEqual(shown(sheet(["F#"]), "G", "F"), ["E"])
        self.assertEqual(shown(sheet(["F#"]), "G", "Bb"), ["A"])
        self.assertEqual(shown(sheet(["C#m"]), "E", "Eb"), ["Cm"])
        # A chord spelled against the key is respelled even without moving.
        self.assertEqual(shown(sheet(["Gb"]), "G"), ["F#"])
        self.assertEqual(shown(sheet(["A#"]), "F"), ["Bb"])

    def test_slash_chords_move_both_notes(self):
        self.assertEqual(shown(sheet(["G/B", "D/F#"]), "G", "A"), ["A/C#", "E/G#"])
        self.assertEqual(shown(sheet(["G/B", "D/F#"]), "G", "Bb"), ["Bb/D", "F/A"])
        self.assertEqual(shown(sheet(["C/E", "Am/G"]), "C", "D"), ["D/F#", "Bm/A"])

    def test_chord_qualities_stay(self):
        names = ["Gmaj7", "Gsus4", "G7", "Gm7b5", "G6/9", "Gadd9", "G(add2)", "Gdim"]
        self.assertEqual(
            shown(sheet(names), "G", "A"),
            ["Amaj7", "Asus4", "A7", "Am7b5", "A6/9", "Aadd9", "A(add2)", "Adim"],
        )

    def test_markers_that_arent_chords_stay(self):
        # An annotation ([*text]) shows its text without the star.
        self.assertEqual(
            shown("[G]la [N.C.]la [*Rit.]la\n", "G", "A"), ["A", "N.C.", "Rit."]
        )

    def test_twelve_steps_up_is_the_same_key(self):
        chord = Chord.parse("D/F#")
        self.assertEqual(str(chord.transposed(12, False)), "D/F#")
        self.assertEqual(str(chord.transposed(-12, False)), "D/F#")


class CapoTests(SimpleTestCase):
    def test_a_capo_shows_the_shapes_played(self):
        rendered = chords.render(sheet(MAJOR_TABLE["A"]), Key.parse("A"), capo=2)
        self.assertEqual(rendered.shape_key.name, "G")
        self.assertEqual(rendered.key.name, "A")  # still heard in A
        self.assertEqual(shown(sheet(MAJOR_TABLE["A"]), "A", capo=2), MAJOR_TABLE["G"])
        self.assertEqual(
            shown(sheet(MAJOR_TABLE["G"]), "G", "Bb", capo=3), MAJOR_TABLE["G"]
        )
        self.assertEqual(shown(sheet(["F#m"]), "A", "Eb", capo=1), ["Bm"])  # D shapes

    def test_capo_positions_and_easy_shapes(self):
        options = chords.capo_options(Key.parse("Bb"))
        self.assertEqual([p for p, _, _ in options], list(range(8)))
        by_position = {p: (shape.name, easy) for p, shape, easy in options}
        self.assertEqual(by_position[1], ("A", True))
        self.assertEqual(by_position[3], ("G", True))
        self.assertEqual(by_position[2], ("Ab", False))

    def test_out_of_range_capo_is_ignored(self):
        self.assertEqual(chords.render(sheet(["G"]), Key.parse("G"), capo=9).capo, 0)


class NashvilleTests(SimpleTestCase):
    def test_the_same_numbers_in_every_major_key(self):
        for key, names in MAJOR_TABLE.items():
            with self.subTest(key=key):
                self.assertEqual(
                    shown(sheet(names), key, numbers=True), ["1", "4", "5", "6m"]
                )

    def test_numbers_follow_the_key_shown_not_the_written_key(self):
        self.assertEqual(
            shown(sheet(MAJOR_TABLE["G"]), "G", "E", numbers=True),
            ["1", "4", "5", "6m"],
        )

    def test_slash_chords_qualities_and_borrowed_chords(self):
        self.assertEqual(
            shown(sheet(["G/B", "Em7", "F", "Cmaj7", "D/F#", "Bb"]), "G", numbers=True),
            ["1/3", "6m7", "b7", "4maj7", "5/7", "b3"],
        )

    def test_in_a_minor_key_one_is_the_minor_tonic(self):
        self.assertEqual(
            shown(sheet(MINOR_TABLE["Am"]), "Am", numbers=True),
            ["1m", "4m", "5m", "b6"],
        )

    def test_numbers_ignore_a_capo(self):
        rendered = chords.render(sheet(["G"]), Key.parse("G"), capo=3, numbers=True)
        self.assertEqual(rendered.capo, 0)


class RenderTests(SimpleTestCase):
    def test_blocks_labels_comments_and_words(self):
        rendered = chords.render(AMAZING_GRACE, Key.parse("G"), Key.parse("A"))
        self.assertEqual(rendered.title, "Amazing Grace")
        self.assertEqual(rendered.subtitle, "John Newton")
        labels = [(b.kind, b.label) for b in rendered.blocks if b.label]
        self.assertEqual(labels, [("verse", "Verse 1"), ("chorus", "Chorus")])
        first = rendered.blocks[0].lines[0].segments
        self.assertEqual(
            [(s.chord, s.text) for s in first],
            [
                ("A", "Amazing "),
                ("A/C#", "grace, how "),
                ("D", "sweet the "),
                ("A", "sound"),
            ],
        )
        comments = [
            line.text
            for b in rendered.blocks
            for line in b.lines
            if line.kind == "comment"
        ]
        self.assertEqual(comments, ["Repeat"])

    def test_words_before_the_first_chord_and_tab_sections(self):
        text = "That [G]saved\n{sot}\ne|--3--[x]--|\n{eot}\n"
        rendered = chords.render(text, Key.parse("G"), Key.parse("A"))
        line = rendered.blocks[0].lines[0]
        self.assertEqual(
            [(s.chord, s.text) for s in line.segments], [("", "That "), ("A", "saved")]
        )
        tab = [b for b in rendered.blocks if b.kind == "tab"][0]
        self.assertEqual(tab.lines[0].text, "e|--3--[x]--|")  # shown as written


class CheckTests(SimpleTestCase):
    def assert_refused(self, text, words):
        with self.assertRaises(ChordProError) as caught:
            chords.check(text)
        self.assertIn(words, str(caught.exception))

    def test_a_valid_sheet_counts_its_chords(self):
        self.assertEqual(chords.check(AMAZING_GRACE), 10)
        self.assertEqual(chords.check("# a comment {not a directive\n[G]la\n"), 1)

    def test_problems_name_their_line(self):
        self.assert_refused("", "empty")
        self.assert_refused("Words only, no chords\n", "no chords")
        self.assert_refused("[G]fine\n[H7]wrong\n", "Line 2: “H7” isn't a chord")
        self.assert_refused("[G]fine\n[G open\n", "Line 2: a chord's [ is never closed")
        self.assert_refused("[G]a]b\n", "Line 1: a ] closes a chord never opened")
        self.assert_refused("[G[C]]\n", "Line 1: a [ opens inside another chord")
        self.assert_refused("[]la\n", "Line 1: [] holds no chord")
        self.assert_refused(
            "[G]la {c: here}\n", "Line 1: a directive must be on its own line"
        )
        self.assert_refused("[G]la }\n", "Line 1:")
        self.assert_refused("{soc}\n[G]la\n", "The chorus at the end is never closed")
        self.assert_refused(
            "{soc}\n{sov}\n[G]la\n", "Line 2: a verse starts before the chorus"
        )
        self.assert_refused(
            "[G]la\n{eoc}\n", "Line 2: this ends a chorus that wasn't started"
        )
        self.assert_refused("[G]la\n" * 4000, "too long")

    def test_the_key_directive(self):
        self.assertEqual(chords.key_directive("{key: Bb}\n[Bb]la\n"), "Bb")
        self.assertEqual(chords.key_directive("[G]la\n"), "")


class ConvertTests(SimpleTestCase):
    def test_chords_over_words_become_chordpro(self):
        chart = (
            "[Verse 1]\n"
            "G       G/B        C         G\n"
            "Amazing grace, how sweet the sound\n"
            "\n"
            "G  D  Em  | x2\n"
        )
        converted = chords.to_chordpro(chart)
        self.assertEqual(
            converted,
            "{comment: Verse 1}\n"
            "[G]Amazing [G/B]grace, how [C]sweet the [G]sound\n"
            "\n"
            "[G]  [D]  [Em]  | x2\n",
        )
        self.assertEqual(chords.check(converted), 7)

    def test_chords_past_the_end_of_the_words(self):
        self.assertEqual(
            chords.to_chordpro("C          G\nLa la\n"), "[C]La la      [G]\n"
        )

    def test_ultimate_guitar_tags_tabs_and_chordpro(self):
        self.assertEqual(
            chords.to_chordpro("[ch]G[/ch]    [ch]C[/ch]\nLa   la\n"), "[G]La   [C]la\n"
        )
        self.assertEqual(chords.to_chordpro("G\tC\nLa  la\n"), "[G]La  [C]la\n")
        already = "{title: Hymn}\n[G]Already [C]ChordPro\n"
        self.assertEqual(chords.to_chordpro(already), already)
        self.assertEqual(
            chords.to_chordpro("[G]Inline [C]chords\n"), "[G]Inline [C]chords\n"
        )

    def test_words_that_look_like_chords_are_left_alone_when_mixed(self):
        # "A" alone is a chord, but a line of words with it is words.
        self.assertEqual(chords.to_chordpro("A new song\n"), "A new song\n")


class RhythmLineTests(SimpleTestCase):
    """Rhythm lines as in Worship Together intros: each slash is a beat."""

    def test_a_rhythm_line_gets_its_chords_in_brackets(self):
        self.assertEqual(
            chords.rhythm_line("|D//G|////|D//G|////|"), "|[D]//[G]|////|[D]//[G]|////|"
        )
        self.assertEqual(
            chords.rhythm_line("Intro: |D//G|////|"), "Intro: |[D]//[G]|////|"
        )
        self.assertEqual(
            chords.rhythm_line("|D/F#//G|Bm7///|"), "|[D/F#]//[G]|[Bm7]///|"
        )

    def test_it_transposes(self):
        converted = chords.to_chordpro("Intro: |D//G|////|D//G|////|\n")
        self.assertEqual(chords.check(converted), 4)
        self.assertEqual(shown(converted, "D", "E"), ["E", "A", "E", "A"])

    def test_an_unreadable_rhythm_line_becomes_a_comment_never_an_error(self):
        for line in ("|D//G|//?//|", "|////|////|"):
            converted = chords.to_chordpro(f"{{key: D}}\n[D]Made up\n{line}\n")
            self.assertIn(f"{{comment: {line}}}", converted)
            chords.check(converted)  # saves

    def test_other_lines_and_tablature_are_left_alone(self):
        for line in ("e|---3---|", "D  G  A", "I | you", "[D]Made up"):
            self.assertIsNone(chords.rhythm_line(line))
        tab = "{key: D}\n[D]Made up\n{sot}\n|---3---|\n{eot}\n"
        self.assertEqual(chords.to_chordpro(tab), tab)

    def test_the_short_key_directive(self):
        self.assertEqual(chords.key_directive("{k: E}\n[E]la\n"), "E")


class BracketedRhythmTests(SimpleTestCase):
    """Worship Together's ChordPro writes a rhythm line inside one bracket:
    "[| D / / G | / / / / |]". Made-up content."""

    SPACED = "[| D / / G | / / / / | D / / G | / / / / |]"

    def test_with_spaces_it_transposes(self):
        self.assertEqual(
            chords.bracketed_rhythm(self.SPACED),
            "| [D] / / [G] | / / / / | [D] / / [G] | / / / / |",
        )
        converted = chords.to_chordpro(f"{{key: D}}\n{self.SPACED}\n[D]Made up\n")
        self.assertEqual(chords.check(converted), 5)
        self.assertEqual(shown(converted, "D", "E"), ["E", "A", "E", "A", "E"])

    def test_without_spaces(self):
        self.assertEqual(chords.bracketed_rhythm("[|D//G|////|]"), "|[D]//[G]|////|")

    def test_with_double_bar_lines(self):
        self.assertEqual(
            chords.bracketed_rhythm("[|| D / / G | / / / / ||]"),
            "|| [D] / / [G] | / / / / ||",
        )

    def test_an_unreadable_one_becomes_a_comment_and_the_sheet_saves(self):
        converted = chords.to_chordpro("{key: D}\n[| D / ? / G |]\n[D]Made up\n")
        self.assertIn("{comment: | D / ? / G |}", converted)
        self.assertEqual(chords.check(converted), 1)

    def test_ordinary_chords_are_left_alone(self):
        for line in ("[D/F#]Made up", "[G]Made [C]up", "Made up words"):
            self.assertIsNone(chords.bracketed_rhythm(line))


class SectionNameTests(SimpleTestCase):
    def test_plain_section_lines_show_as_labels(self):
        text = "{key: D}\nVerse 1\n[D]Made up words\nOutro\n[G]More made up\n"
        converted = chords.to_chordpro(text)
        self.assertIn("{comment: Verse 1}", converted)
        self.assertIn("{comment: Outro}", converted)
        rendered = chords.render(converted, Key.parse("D"))
        labels = [
            line.text
            for b in rendered.blocks
            for line in b.lines
            if line.kind == "comment"
        ]
        self.assertEqual(labels, ["Verse 1", "Outro"])

    def test_names_numbers_and_colons(self):
        for line, label in (
            ("Intro", "Intro"),
            ("Chorus:", "Chorus"),
            ("Bridge 2", "Bridge"),
            ("tag", "tag"),
        ):
            self.assertIn(label, chords.section_line(line))
        self.assertIsNone(chords.section_line("Verse one of a made-up song"))
        self.assertIsNone(chords.section_line("[D]Chorus"))

    def test_in_a_pasted_chart_too(self):
        self.assertEqual(
            chords.to_chordpro("Chorus\nD       G\nMade up words\n"),
            "{comment: Chorus}\n[D]Made up [G]words\n",
        )


class ChartMarkTests(SimpleTestCase):
    """Optional chords, chart marks and unknown marks (made-up content)."""

    def test_an_optional_chord_transposes_and_keeps_its_parentheses(self):
        self.assertEqual(shown("[E]la [(F#m7)]la\n", "E", "F#"), ["F#", "(G#m7)"])
        self.assertEqual(shown("[(D/F#)]la\n", "D", "E"), ["(E/G#)"])
        self.assertEqual(shown("[(F#m7)]la\n", "E", numbers=True), ["(2m7)"])
        self.assertEqual(chords.check("[E]la [(F#m7)]la\n"), 2)

    def test_no_chord_and_repeat_marks_stay_as_written(self):
        text = "[D]la [N.C.]la [x2]la [(x2)]la [n.c.]la\n"
        self.assertEqual(shown(text, "D", "E"), ["E", "N.C.", "x2", "(x2)", "n.c."])
        self.assertEqual(chords.check(text), 1)  # only D is a chord

    def test_a_footnote_mark_stays_and_the_chord_moves(self):
        self.assertEqual(shown("[D*]la [*]la\n", "D", "E"), ["E*", "*"])

    def test_unknown_marks_are_kept_as_annotations(self):
        text, kept = chords.keep_unread(
            "{key: D}\n[D]la\n[Zz9]la [G]la\n{sot}\n[??]\n{eot}\n"
        )
        self.assertEqual(kept, [(3, "Zz9")])
        self.assertIn("[*Zz9]la [G]la", text)
        self.assertIn("[??]", text)  # tablature is left as written
        self.assertEqual(chords.check(text), 2)
        self.assertEqual(shown(text, "D", "E"), ["E", "Zz9", "A"])

    def test_structure_errors_still_stop_a_save(self):
        text, kept = chords.keep_unread("[D]la\n[G open\n")
        self.assertEqual(kept, [])
        with self.assertRaisesMessage(ChordProError, "is never closed"):
            chords.check(text)

    def test_chords_over_words_with_optional_chords(self):
        self.assertEqual(
            chords.to_chordpro("E     (F#m7)\nMade up words\n"),
            "[E]Made u[(F#m7)]p words\n",
        )


class KeptMarkDisplayTests(SimpleTestCase):
    """Marks kept as written are flagged, so the viewer shows them apart and
    notes that they weren't transposed (made-up content)."""

    TEXT = "[D]Made up [*Zz9]words [G]here\n"

    def render(self, target=None, **options):
        return chords.render(
            self.TEXT, Key.parse("D"), Key.parse(target) if target else None, **options
        )

    def test_kept_marks_are_flagged_and_chords_are_not(self):
        segments = self.render("E").blocks[0].lines[0].segments
        self.assertEqual(
            [(s.chord, s.kept) for s in segments],
            [("E", False), ("Zz9", True), ("A", False)],
        )

    def test_the_note_needs_kept_marks_and_a_change_from_the_sheets_key(self):
        self.assertTrue(self.render("E").kept_not_moved)
        self.assertFalse(self.render("D").kept_not_moved)
        self.assertFalse(self.render().kept_not_moved)
        self.assertTrue(self.render(capo=2).kept_not_moved)
        self.assertTrue(self.render(numbers=True).kept_not_moved)
        plain = chords.render(
            "[D]Made up [N.C.]words\n", Key.parse("D"), Key.parse("E")
        )
        self.assertFalse(plain.kept_not_moved)


class StrayBracketTests(SimpleTestCase):
    """A stray ] (a typo such as "[(Em7)]]King") is removed, not an error;
    an unclosed [ still is. Made-up content."""

    def test_a_stray_closing_bracket_is_removed_and_listed(self):
        text, lines = chords.drop_stray_brackets(
            "[D]Made up\n[(Em7)]]King of [G]words]\n"
        )
        self.assertEqual(text, "[D]Made up\n[(Em7)]King of [G]words\n")
        self.assertEqual(lines, [2, 2])
        self.assertEqual(shown(text, "D", "E"), ["E", "(F#m7)", "A"])

    def test_an_unclosed_bracket_is_left_for_the_check(self):
        text, lines = chords.drop_stray_brackets("[D]Made up\n[G open\n")
        self.assertEqual(lines, [])
        with self.assertRaisesMessage(
            ChordProError, "Line 2: a chord's [ is never closed"
        ):
            chords.check(text)

    def test_directives_and_tablature_are_left_alone(self):
        text = "{c: a ] mark}\n{sot}\n|--]--|\n{eot}\n[D]la\n"
        self.assertEqual(chords.drop_stray_brackets(text), (text, []))

    def test_a_rhythm_line_of_chords_without_slashes_transposes(self):
        converted = chords.to_chordpro("{key: G}\n[| Am Bm7 Cmaj7 D |]\n[G]Made up\n")
        self.assertIn("| [Am] [Bm7] [Cmaj7] [D] |", converted)
        self.assertEqual(shown(converted, "G", "A"), ["Bm", "C#m7", "Dmaj7", "E", "A"])
