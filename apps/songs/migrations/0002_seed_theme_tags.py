"""Neutral starting Theme Tags: worship themes most churches sing about.
The church renames them, switches them off or adds its own."""

from django.db import migrations

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


def create(apps, schema_editor):
    ThemeTag = apps.get_model("songs", "ThemeTag")
    if ThemeTag.objects.exists():
        return
    ThemeTag.objects.bulk_create(
        ThemeTag(name=name, keywords=keywords, sort_order=order * 10)
        for order, (name, keywords) in enumerate(TAGS, start=1)
    )


def remove(apps, schema_editor):
    apps.get_model("songs", "ThemeTag").objects.filter(
        name__in=[name for name, _ in TAGS], songs__isnull=True
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("songs", "0001_initial")]

    operations = [migrations.RunPython(create, remove)]
