"""What a new church's song library starts with (Phase 9B, decision 0014).

The same neutral Theme Tags the first church got from migration 0002; the
church renames them, switches them off or adds its own.
"""

TAGS = [
    # name, keywords
    ("Adoration", "adore, worship, praise, glory, worthy, majesty, exalt, bow"),
    ("Thanksgiving", "thank, thanks, thankful, grateful, gratitude, blessing"),
    ("Grace", "grace, gift, undeserved, favor, favour, kindness"),
    ("Forgiveness", "forgive, forgiven, pardon, cleanse, washed, debt"),
    ("Repentance", "repent, repentance, confess, sorry, humble"),
    ("Salvation", "save, saved, savior, saviour, rescue, redeem, redeemed"),
    ("The Cross", "cross, calvary, blood, nails, crucified, sacrifice, lamb"),
    ("Resurrection", "risen, rose, resurrection, tomb, alive, grave, empty"),
    ("Faith", "faith, believe, belief, trust, assurance"),
    ("Hope", "hope, promise, anchor, future, waiting"),
    ("God's Love", "love, loved, beloved, embrace, compassion"),
    ("Loving Others", "neighbor, neighbour, serve, servant, kindness, care"),
    ("Peace", "peace, calm, rest, still, quiet, storm"),
    ("Joy", "joy, rejoice, glad, celebrate, sing, dance"),
    ("Trust", "trust, rely, lean, depend, confidence"),
    ("Surrender", "surrender, surrendered, yield, offering, abandon"),
    ("Holiness", "holy, pure, righteous, sanctified, consecrate"),
    ("God's Faithfulness", "faithful, faithfulness, unchanging, steadfast, sure"),
    ("God's Power", "power, mighty, almighty, strong, strength, victory"),
    ("Creation", "creation, created, earth, sky, stars, sea, mountains"),
    ("Prayer", "pray, prayer, cry, listen, kneel, answer"),
    ("Healing", "heal, healing, healer, whole, restore, broken"),
    ("Comfort", "comfort, tears, sorrow, grief, mourn, weary"),
    ("Guidance", "lead, guide, path, shepherd, follow, lamp"),
    ("Mission", "nations, tell, send, gospel, world, harvest"),
    ("Unity", "together, united, unity, body, family"),
    ("Holy Spirit", "spirit, breath, wind, fire, presence, fill"),
    ("Eternal Life", "heaven, eternity, eternal, forever, crown, everlasting"),
    ("Birth of Jesus", "born, manger, bethlehem, emmanuel, immanuel, child"),
    ("Christ's Return", "return, coming, clouds, trumpet, kingdom, reign"),
]


def seed(church):
    """Theme Tags and Worship Check settings for a new church."""
    from .models import ThemeTag, WorshipCheckSettings

    if not ThemeTag.objects.filter(church=church).exists():
        ThemeTag.objects.bulk_create(
            ThemeTag(church=church, name=name, keywords=keywords, sort_order=n * 10)
            for n, (name, keywords) in enumerate(TAGS, start=1)
        )
    WorshipCheckSettings.load(church)
