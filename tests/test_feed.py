from briefing_skill.feed import parse_feed


def test_atom_parser():
    xml = b'''<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>T</title><id>1</id><updated>2026-01-01T00:00:00Z</updated><link href="https://x"/><summary>S</summary><author><name>A</name></author></entry></feed>'''
    entries = parse_feed(xml)
    assert entries[0].title == "T"
    assert entries[0].link == "https://x"
    assert entries[0].authors == ["A"]
