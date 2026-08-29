from PIL import Image, ImageDraw
from pathlib import Path

katalog = Path("/srv/app/app/static/ikony")
katalog.mkdir(parents=True, exist_ok=True)

for bok in (192, 512):
    s = bok / 512
    obraz = Image.new("RGB", (bok, bok), "#212529")
    rys = ImageDraw.Draw(obraz)
    rys.polygon([(60*s, 400*s), (140*s, 250*s), (372*s, 250*s), (452*s, 400*s)],
                fill="#343a40")
    rys.line([(90*s, 330*s), (422*s, 375*s)], fill="#0d6efd", width=int(46*s))
    rys.line([(90*s, 330*s), (422*s, 375*s)], fill="#8bb9ff", width=int(10*s))
    rys.rectangle([236*s, 90*s, 276*s, 340*s], fill="#f8f9fa")
    for i in range(5):
        y = (110 + i * 46) * s
        rys.rectangle([236*s, y, 276*s, y + 23*s], fill="#dc3545")
    obraz.save(katalog / f"ikona-{bok}.png")
    print("zapisano", katalog / f"ikona-{bok}.png")
