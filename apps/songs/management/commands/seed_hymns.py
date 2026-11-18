"""Seed the song pool with public-domain hymns, to try suggestions without
Spotify (Development Plan, Phase 5).

Only public-domain words may be seeded (AGENTS.md): every text here was
first published before 1913. The hymns have no Spotify track; their lyrics
count as found, so the search worker (or ``process_songs``) analyses them,
and a "Rank the song pool only" run can suggest them.
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.songs.models import Song

# (title, author and year, words)
HYMNS = [
    (
        "Amazing Grace",
        "John Newton (1779)",
        """Amazing grace! how sweet the sound
That saved a wretch like me!
I once was lost, but now am found,
Was blind, but now I see.

'Twas grace that taught my heart to fear,
And grace my fears relieved;
How precious did that grace appear
The hour I first believed!

Through many dangers, toils and snares,
I have already come;
'Tis grace hath brought me safe thus far,
And grace will lead me home.""",
    ),
    (
        "Holy, Holy, Holy",
        "Reginald Heber (1826)",
        """Holy, holy, holy! Lord God Almighty!
Early in the morning our song shall rise to thee;
Holy, holy, holy! merciful and mighty!
God in three Persons, blessed Trinity!

Holy, holy, holy! all the saints adore thee,
Casting down their golden crowns around the glassy sea;
Cherubim and seraphim falling down before thee,
Which wert, and art, and evermore shalt be.""",
    ),
    (
        "It Is Well with My Soul",
        "Horatio Spafford (1873)",
        """When peace, like a river, attendeth my way,
When sorrows like sea billows roll;
Whatever my lot, thou hast taught me to say,
It is well, it is well with my soul.

It is well with my soul,
It is well, it is well with my soul.

Though Satan should buffet, though trials should come,
Let this blest assurance control,
That Christ hath regarded my helpless estate,
And hath shed his own blood for my soul.""",
    ),
    (
        "Come, Thou Fount of Every Blessing",
        "Robert Robinson (1758)",
        """Come, thou Fount of every blessing,
Tune my heart to sing thy grace;
Streams of mercy, never ceasing,
Call for songs of loudest praise.
Teach me some melodious sonnet,
Sung by flaming tongues above.
Praise the mount! I'm fixed upon it,
Mount of thy redeeming love.""",
    ),
    (
        "Rock of Ages",
        "Augustus Toplady (1776)",
        """Rock of Ages, cleft for me,
Let me hide myself in thee;
Let the water and the blood,
From thy wounded side which flowed,
Be of sin the double cure;
Save from wrath and make me pure.

Not the labours of my hands
Can fulfil thy law's demands;
Could my zeal no respite know,
Could my tears for ever flow,
All for sin could not atone;
Thou must save, and thou alone.""",
    ),
    (
        "Joyful, Joyful, We Adore Thee",
        "Henry van Dyke (1907)",
        """Joyful, joyful, we adore thee,
God of glory, Lord of love;
Hearts unfold like flowers before thee,
Opening to the sun above.
Melt the clouds of sin and sadness;
Drive the dark of doubt away;
Giver of immortal gladness,
Fill us with the light of day!""",
    ),
    (
        "Blessed Assurance",
        "Fanny Crosby (1873)",
        """Blessed assurance, Jesus is mine!
O what a foretaste of glory divine!
Heir of salvation, purchase of God,
Born of his Spirit, washed in his blood.

This is my story, this is my song,
Praising my Saviour all the day long;
This is my story, this is my song,
Praising my Saviour all the day long.""",
    ),
    (
        "What a Friend We Have in Jesus",
        "Joseph Scriven (1855)",
        """What a friend we have in Jesus,
All our sins and griefs to bear!
What a privilege to carry
Everything to God in prayer!
O what peace we often forfeit,
O what needless pain we bear,
All because we do not carry
Everything to God in prayer.""",
    ),
    (
        "Crown Him with Many Crowns",
        "Matthew Bridges (1851)",
        """Crown him with many crowns,
The Lamb upon his throne;
Hark! how the heavenly anthem drowns
All music but its own.
Awake, my soul, and sing
Of him who died for thee,
And hail him as thy matchless King
Through all eternity.""",
    ),
]


def seed_hymns():
    """Add the hymns the pool doesn't have yet; returns how many were added."""
    added = 0
    now = timezone.now()
    with transaction.atomic():
        for title, author, words in HYMNS:
            _, created = Song.objects.get_or_create(
                title=title,
                artist=author,
                spotify_id="",
                defaults={
                    "lyrics": words,
                    "lyrics_status": Song.LyricsStatus.FOUND,
                    "lyrics_checked_at": now,
                },
            )
            added += created
    return added


class Command(BaseCommand):
    help = (
        "Add public-domain hymns to the song pool, to try suggestions without "
        "Spotify. Running it again adds only hymns that are missing."
    )

    def handle(self, *args, **options):
        added = seed_hymns()
        self.stdout.write(
            self.style.SUCCESS(
                f"Added {added} of {len(HYMNS)} public-domain hymns. Run the search "
                "worker (or process_songs) to analyse them."
            )
        )
