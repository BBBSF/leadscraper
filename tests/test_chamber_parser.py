from bbb_lead_scraper.sources.chamber_growthzone import GrowthZoneDirectorySource


def test_parse_growthzone_like_listing():
    html = """
    <html><body>
      <div class="mn-listing">
        <h5><a href="/member/acme-roofing">Acme Roofing Co.</a></h5>
        <ul><li>123 Main St San Francisco CA 94103</li><li>(415) 555-1212</li></ul>
      </div>
    </body></html>
    """
    src = GrowthZoneDirectorySource("sf_chamber", {"base_url": "https://business.example.com/list"})
    records = src._parse_page(html, "https://business.example.com/list/searchalpha/a")
    assert len(records) == 1
    assert records[0]["business_name"] == "Acme Roofing Co."
    assert records[0]["phone"] == "(415) 555-1212"
    assert records[0]["zip"] == "94103"
    assert records[0]["record_url"] == "https://business.example.com/member/acme-roofing"
