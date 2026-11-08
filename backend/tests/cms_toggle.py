"""Helper: apply/restore CMS test changes (contact WA, visible service, reorder home). Usage: python cms_toggle.py apply|restore"""
import json
import sys
import requests
from conftest import BASE_URL

B = BASE_URL + "/api"
s = requests.Session()
s.post(f"{B}/auth/login", json={"email": "admin.test@predator.local", "password": "AdminUji#2026"})
cms = {d["key"]: d for d in s.get(f"{B}/cms").json()}
SNAP = "/tmp/cms_snapshot.json"
if sys.argv[1] == "apply":
    json.dump({k: cms[k]["published"] for k in ("contact", "services", "home")} |
              {"_draft": {k: cms[k]["draft"] for k in ("contact", "services", "home")}}, open(SNAP, "w"))
    c = dict(cms["contact"]["published"]) | {"whatsapp": "6281999888777"}
    print("contact", s.put(f"{B}/cms/contact", json={"data": c}).status_code, s.post(f"{B}/cms/contact/publish").status_code)
    sv = {"items": list(cms["services"]["published"].get("items", [])) + [{
        "title": "TEST Layanan Pasang BiLED", "slug": "test-biled", "description": "uji", "image": "", "price": 1000000,
        "price_text": "", "features": [], "addons": [], "featured": True, "visible": True}]}
    print("services", s.put(f"{B}/cms/services", json={"data": sv}).status_code, s.post(f"{B}/cms/services/publish").status_code)
    secs = list(cms["home"]["published"]["sections"])
    faq = next(x for x in secs if x["type"] == "faq")
    secs.remove(faq)
    secs.insert(1, faq)
    print("home", s.put(f"{B}/cms/home", json={"data": {"sections": secs}}).status_code, s.post(f"{B}/cms/home/publish").status_code)
    print("order", [x["type"] for x in s.get(f"{B}/public/site").json()["home"]["sections"]])
    revs = s.get(f"{B}/cms/contact/revisions").json()
    print("contact revisions", len(revs), [r["kind"] for r in revs[:3]])
else:
    snap = json.load(open(SNAP))
    for k in ("contact", "services", "home"):
        s.put(f"{B}/cms/{k}", json={"data": snap[k]})
        s.post(f"{B}/cms/{k}/publish")
        s.put(f"{B}/cms/{k}", json={"data": snap["_draft"][k]})
    # test restore endpoint: restore latest contact draft revision
    revs = s.get(f"{B}/cms/contact/revisions").json()
    r = s.post(f"{B}/cms-revisions/{revs[0]['id']}/restore")
    print("restore endpoint", r.status_code)
    pub = s.get(f"{B}/public/site").json()
    print("restored wa:", repr(pub["contact"]["whatsapp"]), "services:", [i["title"] for i in pub["services"]["items"]],
          "order:", [x["type"] for x in pub["home"]["sections"]])
