import pytest

from src.forecast_discussion_notifier.notifier import notify_discord, MesoscaleDiscussion

TEST_WEBHOOK_URL = "https://discord.com/api/webhooks/1253666695667519540/wr44A-qYHt98mCLB8iuDUBfIIEipO0vyUcVXOeiXkn1H1x1VkS4sstB7u2ZW_gGca2U2"

@pytest.fixture
def test_md():
    return MesoscaleDiscussion(
        id=1,
        info_page="https://www.spc.noaa.gov/products/md/md0001.html",
        geometry={"type": "Point", "coordinates": [-94.5, 38.5]},
    )

def test_notify_discord(test_md):
    status_code: int = notify_discord(test_md, TEST_WEBHOOK_URL)
    assert status_code == 204