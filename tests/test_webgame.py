"""server/webgame.py: paths of the browser version (page, game files, storage layers, no escaping the folders)."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))
from webgame import WebGame  # noqa: E402


def main():
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        (t / "web" / "game" / "config").mkdir(parents=True)
        (t / "web" / "game" / "MobileGame.swf").write_bytes(b"swf")
        (t / "web" / "game" / "config" / "mmog.xml").write_text("x")
        (t / "web" / "storage" / "asset" / "cards").mkdir(parents=True)
        (t / "web" / "storage" / "asset" / "cards" / "revival9001_1.jpg").write_bytes(b"new")
        (t / "ls" / "asset" / "cards").mkdir(parents=True)
        (t / "ls" / "asset" / "cards" / "4007_1.jpg").write_bytes(b"old")
        (t / "ls" / "asset" / "cards" / "revival9001_1.jpg").write_bytes(b"shadowed")
        (t / "ruffle").mkdir()
        (t / "ruffle" / "ruffle.js").write_text("js")
        (t / "secret.txt").write_text("no")
        g = WebGame(str(t / "web"), str(t / "ls"), str(t / "ruffle"))

        assert g.available()
        assert g.resolve("/bam") == ("redirect", "/bam/")
        assert g.resolve("/bam/")[0] == "page" and b"revivalLogin" in g.resolve("/bam/")[1]
        assert g.resolve("/bam/index.html")[0] == "page"
        assert g.resolve("/facebook/proxy.html") is None and g.resolve("/fb/dialog/oauth") is None
        assert g.resolve("/bam/MobileGame.swf") == ("file", t / "web" / "game" / "MobileGame.swf")
        assert g.resolve("/bam/config/mmog.xml?x=1")[0] == "file"
        assert g.resolve("/bam/ruffle/ruffle.js")[0] == "file"
        # storage: our packages first, then the original content; case-insensitive like a phone
        assert g.resolve("/bam/storage/asset/cards/revival9001_1.jpg")[1].read_bytes() == b"new"
        assert g.resolve("/bam/storage/asset/cards/4007_1.JPG")[1].read_bytes() == b"old"
        assert g.resolve("/bam/storage/asset/cards/none.jpg") == ("missing", None)
        # no way out of the folders
        for bad in ("/bam/../secret.txt", "/bam/storage/../../secret.txt", "/bam/ruffle/../../secret.txt",
                    "/bam/C:/Windows/win.ini", "/bam/storage/..\\..\\secret.txt"):
            assert g.resolve(bad) == ("missing", None), bad
        assert WebGame.content_type(Path("a.wasm")) == "application/wasm"
        assert WebGame.cache_control("file", Path("MobileGame.swf")) == "no-cache"

        assert not WebGame("", str(t / "ls"), "").available()  # not built: the server answers 404 for the page
    print("test_webgame: all OK")


if __name__ == "__main__":
    main()
