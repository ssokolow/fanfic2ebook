from fanfic2ebook.data_structures import Story, Chapter

def setup(self):
    _c = Story('MyTitle', 'MyAuthor')
    _c.author_url = "http://www.author.com/"
    _c.story_url = "http://www.author.com/story/"
    _c.publisher = "FicSite"

    self.empty_story = Story(None, None)
    self.chapterless_story = _c
