import os
from concurrent.futures import ThreadPoolExecutor

import dotenv

from storygrabber.lazylibrarian import LazyLibrarianClient

dotenv.load_dotenv()
ll_host = os.getenv("LL_HOST", "localhost")
ll_port = int(os.getenv("LL_PORT", "5299"))
ll_api_key = os.getenv("LL_API_KEY", "")
ll_use_https = os.getenv("LL_HTTPS", "False").lower() == "true"
ll = LazyLibrarianClient(
    host=ll_host,
    port=ll_port,
    api_key=ll_api_key,
    use_https=ll_use_https,
)

print(ll.get_author("6519144"))
authors = ll.get_all_authors()
print(authors.keys())
del_authors = []
for a in authors["data"]:
    if isinstance(a, dict):
        reason = a.get("Reason", "")
        if reason and isinstance(reason, str) and "Series" in reason:
            if not a.get("HaveBooks", 1) > 0:
                del_authors.append(a.get("AuthorID", str(a)))

with ThreadPoolExecutor(max_workers=6) as executor:
    executor.map(ll.remove_author, del_authors)
