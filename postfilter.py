from datetime import datetime
import pytz
def datefilter(articles):
    now = datetime.now().replace(tzinfo=pytz.UTC)
    return filter(lambda x: now > x.date.replace(tzinfo=pytz.UTC), articles)