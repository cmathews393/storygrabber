from bs4 import BeautifulSoup
from storygrab.modules.storygraph import StoryGrabber

SAMPLE_HTML = """
<div class="max-w-3xl mb-4 md:mb-6 text-darkestGrey dark:text-grey book-pane break-words" id="book_ff94854a-ad06-45c4-8de3-acc7050364ba" data-book-id="ff94854a-ad06-45c4-8de3-acc7050364ba" data-author-ids="535ebad3-355a-44e0-86d4-d2b4cce10be3">
  <div class="hidden md:block">
    <div class="book-pane-content border border-darkGrey dark:border-darkerGrey rounded">
      <div class="grid grid-cols-12 gap-4 p-4">
        <div class="col-span-2 cover-image-column">
            <div class="book-cover">
              <a href="/books/ff94854a-ad06-45c4-8de3-acc7050364ba">
                <img alt="Under the Eye of Power: How Fear of Secret Societies Shapes American Democracy by Colin Dickey" class="rounded-sm shadow-lg dark:shadow-darkerGrey/40" src="https://cdn.thestorygraph.com/alaaa0bgj2pazmpv34sq3dtnbr0d">
</a>              </div>
        </div>

        <div class="col-span-6 w-[93%]">
          <div class="book-title-author-and-series">
            <h3 class="font-bold text-xl"><span class="text-red-700 dark:text-red-200"></span><a href="/books/ff94854a-ad06-45c4-8de3-acc7050364ba">Under the Eye of Power: How Fear of Secret Societies Shapes American Democracy</a>
              
              
              

              <p class="font-body mb-1 mt-1 md:mt-0 text-sm font-medium">
              <a class="hover:text-cyan-700, dark:hover:text-cyan-500" href="/authors/535ebad3-355a-44e0-86d4-d2b4cce10be3">Colin Dickey</a>
              </p>
            </h3></div>
        </div>
      </div>
    </div>
  </div>
</div>
"""


def test_extract_books_from_sample_html():
    soup = BeautifulSoup(SAMPLE_HTML, "html.parser")
    sg = StoryGrabber("dummy_user", session_id="test")
    seen = set()
    books = sg._extract_books_from_soup(soup, seen)

    assert isinstance(books, list)
    assert len(books) == 1
    url, title, author = books[0]
    assert "Under the Eye of Power" in title
    assert "Colin Dickey" in author
    assert url.startswith("https://app.thestorygraph.com/books/")
