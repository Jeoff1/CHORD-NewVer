"""Seed the song pool with public-domain hymns and carols, to try
suggestions without Spotify (Development Plan, Phase 5).

Only public-domain words may be seeded (AGENTS.md): every text here was
first published before 1913 (public domain in the United States), and every
author and translator died more than 70 years ago, the latest being Henry
van Dyke in 1933 (public domain where copyright lasts the author's life
plus 70 years). The hymns have no Spotify track; their
lyrics count as found, so the search worker (or ``process_songs``)
analyses them, and a "Rank the song pool only" run can suggest them.

There are general hymns, Christmas carols, slow hymns and Easter hymns, so
themes across the year find something.
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
    # Christmas carols
    (
        "Joy to the World",
        "Isaac Watts (1719)",
        """Joy to the world! the Lord is come;
Let earth receive her King;
Let every heart prepare him room,
And heaven and nature sing,
And heaven and nature sing,
And heaven, and heaven, and nature sing.

Joy to the earth! the Saviour reigns;
Let men their songs employ;
While fields and floods, rocks, hills and plains
Repeat the sounding joy,
Repeat the sounding joy,
Repeat, repeat the sounding joy.""",
    ),
    (
        "Hark! the Herald Angels Sing",
        "Charles Wesley (1739)",
        """Hark! the herald angels sing,
Glory to the newborn King;
Peace on earth, and mercy mild,
God and sinners reconciled!
Joyful, all ye nations, rise,
Join the triumph of the skies;
With the angelic host proclaim,
Christ is born in Bethlehem!
Hark! the herald angels sing,
Glory to the newborn King!""",
    ),
    (
        "Silent Night",
        "Joseph Mohr (1818), tr. John F. Young (1859)",
        """Silent night, holy night,
All is calm, all is bright
Round yon virgin mother and child.
Holy infant so tender and mild,
Sleep in heavenly peace,
Sleep in heavenly peace.

Silent night, holy night,
Shepherds quake at the sight;
Glories stream from heaven afar,
Heavenly hosts sing Alleluia!
Christ the Saviour is born,
Christ the Saviour is born!""",
    ),
    (
        "O Come, All Ye Faithful",
        "J. F. Wade, tr. Frederick Oakeley (1841)",
        """O come, all ye faithful,
Joyful and triumphant,
O come ye, O come ye to Bethlehem;
Come and behold him,
Born the King of angels:
O come, let us adore him,
O come, let us adore him,
O come, let us adore him,
Christ the Lord.""",
    ),
    (
        "O Little Town of Bethlehem",
        "Phillips Brooks (1868)",
        """O little town of Bethlehem,
How still we see thee lie!
Above thy deep and dreamless sleep
The silent stars go by.
Yet in thy dark streets shineth
The everlasting Light;
The hopes and fears of all the years
Are met in thee tonight.""",
    ),
    (
        "The First Noel",
        "Traditional (1823)",
        """The first Noel the angel did say
Was to certain poor shepherds in fields as they lay;
In fields where they lay keeping their sheep,
On a cold winter's night that was so deep.
Noel, Noel, Noel, Noel,
Born is the King of Israel.""",
    ),
    (
        "Angels We Have Heard on High",
        "Traditional, tr. James Chadwick (1862)",
        """Angels we have heard on high,
Sweetly singing o'er the plains,
And the mountains in reply
Echoing their joyous strains.
Gloria in excelsis Deo!
Gloria in excelsis Deo!""",
    ),
    (
        "What Child Is This",
        "William Chatterton Dix (1865)",
        """What child is this, who, laid to rest,
On Mary's lap is sleeping?
Whom angels greet with anthems sweet,
While shepherds watch are keeping?
This, this is Christ the King,
Whom shepherds guard and angels sing;
Haste, haste to bring him laud,
The babe, the son of Mary.""",
    ),
    # Slow hymns
    (
        "Abide with Me",
        "Henry Francis Lyte (1847)",
        """Abide with me; fast falls the eventide;
The darkness deepens; Lord, with me abide;
When other helpers fail and comforts flee,
Help of the helpless, O abide with me.

Swift to its close ebbs out life's little day;
Earth's joys grow dim, its glories pass away;
Change and decay in all around I see;
O thou who changest not, abide with me.""",
    ),
    (
        "Just As I Am",
        "Charlotte Elliott (1835)",
        """Just as I am, without one plea,
But that thy blood was shed for me,
And that thou bidst me come to thee,
O Lamb of God, I come, I come.

Just as I am, and waiting not
To rid my soul of one dark blot,
To thee whose blood can cleanse each spot,
O Lamb of God, I come, I come.""",
    ),
    (
        "Be Still, My Soul",
        "Katharina von Schlegel, tr. Jane Borthwick (1855)",
        """Be still, my soul: the Lord is on thy side;
Bear patiently the cross of grief or pain;
Leave to thy God to order and provide;
In every change he faithful will remain.
Be still, my soul: thy best, thy heavenly Friend
Through thorny ways leads to a joyful end.""",
    ),
    (
        "When I Survey the Wondrous Cross",
        "Isaac Watts (1707)",
        """When I survey the wondrous cross
On which the Prince of glory died,
My richest gain I count but loss,
And pour contempt on all my pride.

Were the whole realm of nature mine,
That were an offering far too small;
Love so amazing, so divine,
Demands my soul, my life, my all.""",
    ),
    # Easter hymns
    (
        "Christ the Lord Is Risen Today",
        "Charles Wesley (1739)",
        """Christ the Lord is risen today, Alleluia!
Sons of men and angels say, Alleluia!
Raise your joys and triumphs high, Alleluia!
Sing, ye heavens, and earth, reply, Alleluia!

Love's redeeming work is done, Alleluia!
Fought the fight, the battle won, Alleluia!
Death in vain forbids him rise, Alleluia!
Christ has opened paradise, Alleluia!""",
    ),
    (
        "Low in the Grave He Lay",
        "Robert Lowry (1874)",
        """Low in the grave he lay,
Jesus my Saviour,
Waiting the coming day,
Jesus my Lord!

Up from the grave he arose,
With a mighty triumph o'er his foes;
He arose a victor from the dark domain,
And he lives forever, with his saints to reign.
He arose! He arose!
Hallelujah! Christ arose!""",
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
