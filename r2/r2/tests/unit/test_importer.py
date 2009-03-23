# -*- coding: utf-8 -*-
import nose

from r2.tests import ModelTest

from r2.lib.db.thing import NotFound

import r2.lib.importer
from r2.lib.importer import AtomImporter

import re
import gdata
from gdata import atom

DUMMY_EMAIL = 'test@lesswrong.com'
DUMMY_URI = 'http://www.lesswrong.com/'
ATOM_TYPE = 'application/atom+xml'
HTML_TYPE = 'text/html'
CATEGORY_NS = 'http://www.blogger.com/atom/ns#'
CATEGORY_KIND = 'http://schemas.google.com/g/2005#kind'
POST_KIND = 'http://schemas.google.com/blogger/2008/kind#post'
COMMENT_KIND = 'http://schemas.google.com/blogger/2008/kind#comment'
ATOM_THREADING_NS = 'http://purl.org/syndication/thread/1.0'

class InReplyTo(atom.ExtensionElement):
  """Supplies the in-reply-to element from the Atom threading protocol."""

  def __init__(self, ref, href=None):
    """Constructs an InReplyTo element."""
    attrs = {}
    attrs['ref'] = ref
    attrs['type'] = ATOM_TYPE
    if href:
      attrs['href'] = href
    atom.ExtensionElement.__init__(self, 'in-reply-to',
                                   namespace=ATOM_THREADING_NS,
                                   attributes=attrs)

class AtomFeedFixture(object):

    def __init__(self, title='Feed Fixture', url='http://www.lesswrong.com/.rss', alternate_url='http://www.lesswrong.com/'):
        # Create the top-level feed object
        feed = gdata.GDataFeed()

        # Fill in the feed object with the boilerplate metadata
        feed.generator = atom.Generator(text='Blogger')
        feed.title = atom.Title(text=title)
        feed.link.append(
            atom.Link(href=url, rel='self', link_type=ATOM_TYPE))
        feed.link.append(
            atom.Link(href=alternate_url, rel='alternate', link_type=HTML_TYPE))
        self.feed = feed
        self.ids  = {}

    #TODO Need an author generator: name, email
    def _add_entry(self, entry_id, kind, author='Anonymous', content='', **kw):
        entry = gdata.GDataEntry()
        entry.link.append(
            atom.Link(href=DUMMY_URI, rel='self', link_type=ATOM_TYPE))
        entry.link.append(
            atom.Link(href=DUMMY_URI, rel='alternate', link_type=HTML_TYPE))

        # Add the author
        #author_name = self._Encode(value)
        entry.author = atom.Author(atom.Name(text=author))

        # Add the content
        entry.content = atom.Content(
            content_type='html', text=content)
            # content_type='html', text=self._TranslateContents(tag_contents))

        # Add the kind
        entry.category.append(
            atom.Category(scheme=CATEGORY_KIND, term=kind))

        if kind == COMMENT_KIND:
            # Add the post id to the comment
            entry.extension_elements.append(InReplyTo(kw['post_id']))

        # Add the id of the entry
        entry.id = atom.Id(entry_id)
        self.feed.entry.append(entry)
        return entry_id

    def add_post(self, **kw):
        post_id = self.post_id
        return self._add_entry(post_id, POST_KIND, **kw)

    def add_comment(self, post_id, **kw):
        comment_id = self.comment_id
        return self._add_entry(comment_id, COMMENT_KIND, post_id=post_id, **kw)

    def __getattr__(self, attr):
        if attr.endswith('_id'):
            self.ids[attr] = self.ids.get(attr, 0) + 1
            return "%s-%d" % (attr[:-3], self.ids[attr])
        else:
            raise AttributeError, '%s not found' % attr

    def __str__(self):
        # Return self an an XML atom feed string
        # print str(self.feed)
        return str(self.feed)

class TestAtomImporter(object):

    def test_posts_by_author(self):
        feed = AtomFeedFixture()
        for author in ['Joe Bloggs','Not Joe Bloggs','Joe Bloggs','Someone Else']:
            feed.add_post(author=author)
        importer = AtomImporter(str(feed))
        post_ids = [post.id.text for post in importer.posts_by(['Joe Bloggs'])]
        assert post_ids == ['post-1','post-3']

    def test_posts_by_authors(self):
        feed = AtomFeedFixture()
        for author in ['Joe Bloggs','Steve Jobs','Not Joe Bloggs','Jane Smith','Bill Gates','John Smith','Bill Gates']:
            feed.add_post(author=author)
        importer = AtomImporter(str(feed))
        post_ids = [post.id.text for post in importer.posts_by(['Steve Jobs', 'Bill Gates'])]
        assert post_ids == ['post-2','post-5','post-7']

    def test_comments_on_post(self):
        feed = AtomFeedFixture()
        post1 = feed.add_post()
        comment1 = feed.add_comment(post1)
        post2 = feed.add_post()
        comment2 = feed.add_comment(post2)
        comment3 = feed.add_comment(post1)
        importer = AtomImporter(str(feed))
        comment_ids = [comment.id.text for comment in importer.comments_on_post(post1)]
        assert comment_ids == [comment1, comment3]


    url_content = (
        ('Some text', 'Some text'),
        ('Blah <a href="http://www.overcomingbias.com/2007/11/passionately-wr.html">Link</a> more',
            'Blah <a href="http://www.overcomingbias-rewritten.com/2007/11/passionately-wr.html">Link</a> more'),
        ('Multiple urls: http://www.overcomingbias.com/ and http://overcomingbias.com and http://google.com/?q=test',
            'Multiple urls: http://www.overcomingbias-rewritten.com/ and http://overcomingbias-rewritten.com and http://google.com/?q=test'),
        ('Query string: http://www.google.com/search?rls=en-us&q=overcomingbias&ie=UTF-8&oe=UTF-8',
            'Query string: http://www.google.com/search?rls=en-us&q=overcomingbias-rewritten&ie=UTF-8&oe=UTF-8'),
        ('IP Address: http://72.14.235.104/?q=overcomingbias',
            'IP Address: http://72.14.235.104/?q=overcomingbias-rewritten'),
        ('Google cache: http://72.14.235.132/search?client=safari&rls=en-us&q=cache:http://www.overcomingbias.com/2007/11/passionately-wr.html&ie=UTF-8&oe=UTF-8',
            'Google cache: http://72.14.235.132/search?client=safari&rls=en-us&q=cache:http://www.overcomingbias-rewritten.com/2007/11/passionately-wr.html&ie=UTF-8&oe=UTF-8'),
        ("""Overcoming Bias links: http://www.overcomingbias.com
            http://www.overcomingbias.com/
            http://www.overcomingbias.com/2006/11/beware_heritabl.html
            http://www.overcomingbias.com/2006/11/beware_heritabl.html#comment-25685746""",
        """Overcoming Bias links: http://www.overcomingbias-rewritten.com
            http://www.overcomingbias-rewritten.com/
            http://www.overcomingbias-rewritten.com/2006/11/beware_heritabl.html
            http://www.overcomingbias-rewritten.com/2006/11/beware_heritabl.html#comment-25685746"""),
        ('Unicode: (http://www.overcomingbias.com/ÜnîCöde¡っ)', 'Unicode: (http://www.overcomingbias-rewritten.com/ÜnîCöde¡っ)'),
    )
    
    @staticmethod
    def url_rewriter(match):
        # This replacement will deliberately match again if the importer
        # processes the same url twice 
        return match.group().replace('overcomingbias', 'overcomingbias-rewritten')

    def test_rewrite_urls_in_post_body(self):
        for input_content, expected_content in self.url_content:
            feed = AtomFeedFixture()
            post = feed.add_post(content=input_content)
            importer = AtomImporter(str(feed), url_handler=self.url_rewriter)
            yield self.check_text, importer.get_post(post).content.text, expected_content

    @staticmethod
    def check_text(text, expected_text):
        assert text == expected_text
    
    def test_rewrite_urls_in_comments(self):
        for input_content, expected_content in self.url_content:
            feed = AtomFeedFixture()
            post = feed.add_post()
            feed.add_comment(post_id=post, content=input_content)
            importer = AtomImporter(str(feed), url_handler=self.url_rewriter)
            for comment in importer.comments_on_post(post):
                yield self.check_text, comment.content.text, expected_content

    pw_re = re.compile(r'[1-9a-hjkmnp-uwxzA-HJKMNP-UWXZ@#$%^&*]{8}')
    def test_generate_password(self):
        
        # This test is a bit questionable given the random generation
        # but its better than no test
        for i in range(10):
            password = r2.lib.importer.generate_password()
            # print password
            assert self.pw_re.match(password)


    # def test_username_from_name(self):
    #     feed = AtomFeedFixture()
    #     post = feed.add_post()
    #     importer = AtomImporter(str(feed))
    #     
    #     names = (
    #         ('First Last', 'First_Last'), # Spaces
    #         ('~O~','~O~'),
    #         ('Øyvind','Øyvind'),
    #         ('x-ray fluorescence','x-ray_fluorescence'),
    #         ('"Q" the Enchanter', 'Q_the_Enchanter'),
    #         ('(Hope)Fully Rational', 'HopeFully_Rational'),
    #         ('-', '-'),
    #         ('-ck-', '-ck-'),
    #         ('-dan', '-dan'),
    #         ('...', '...'),
    #         ('.5%', '.5%'),
    #         ('/ehj2', '/ehj2'),
    #         ('01', '01'),
    #         ('3.14159', '3.14159'),
    #         ('4σ', '4σ'),
    #         ('51a1fc26f78b0296a69f53c615ab5a2f64ab1d1e', '51a1fc26f78b0296a69f53c615ab5a2f64ab1d1e'),
    #         ('?', '?'),
    #         ('????a', '????a'),
    #         ('A woman\'s POV', 'A woman\'s POV'),
    #         ('A. Coward', 'A. Coward'),
    #         ('A.B.', 'A.B.'),
    #         ('A.S. (a hikikomori from Russia)', 'A.S. (a hikikomori from Russia)'),
    #         ('AW', 'AW'),
    #         ('Abdullah Khalid Siddiqi', 'Abdullah Khalid Siddiqi'),
    #         ('Agent00yak', 'Agent00yak'),
    #         ('Alexander Fiske-Harrison', 'Alexander Fiske-Harrison'),
    #         ('Anon of /co/ and /tg/', 'Anon of /co/ and /tg/'),
    #         ('Another somewhat sceptical statistician', 'Another somewhat sceptical statistician'),
    #         ('Anónima', 'Anónima'),
    #         ('Awww, a girlfriend > Singularity', 'Awww, a girlfriend > Singularity'),
    #         ('Faré', 'Faré'),
    #         ('Firozali A Mulla MBA PhD', 'Firozali A Mulla MBA PhD'),
    #         ('Firozali A.Mulla  MBA PhD', 'Firozali A.Mulla  MBA PhD'),
    #         ('Franklin D. Fields, Jr.', 'Franklin D. Fields, Jr.'),
    #         ('Geebu$', 'Geebu$'),
    #         ('Hmm...', 'Hmm...'),
    #         ('Hoàng Đức Hiếu', 'Hoàng Đức Hiếu'),
    #         ('Håkan Andersson', 'Håkan Andersson'),
    #         ('MyMindOnMyMoney & MyMoneyOnMyMind', 'MyMindOnMyMoney & MyMoneyOnMyMind'),
    #         ('Santa Claus (is my legal name)', 'Santa Claus (is my legal name)'),
    #         ('Z Z z z z e x ...', 'Z Z z z z e x ...'),
    #         ('_Felix', '_Felix'),
    #         ('____', '____'),
    #         ('jaltcoh.blogspot.com', 'jaltcoh.blogspot.com'),
    #         ('spindizzy@eml.cc', 'spindizzy@eml.cc'),
    #     )
    #     for name, username in names:
    #         yield self.check_text, importer._username_from_name(name), username
        
    def test_set_sort_order(self):
        pass
    
    def test_filter_html_in_titles(self):
        pass
    
    def test_set_comment_is_html(self):
        pass
    
    def test_auto_account_creation(self):
        pass
    
    def test_cleaning_of_content(self):
        # There are a lot of ^M's in the comments
        pass

from mocktest import *
from r2.models import Account
from r2.models.account import AccountExists
class TestAtomImporterMocktest(TestCase):
    
    @property
    def importer(self):
        feed = AtomFeedFixture()
        post = feed.add_post()
        feed.add_comment(post_id=post)

        return AtomImporter(
            str(feed),
        )

    def test_get_or_create_account_exists(self):
        anchor = mock_on(Account)
        account = mock_wrapper().with_methods(_safe_load=None)
        anchor._query.returning([account.mock]).is_expected
        assert self.importer._get_or_create_account('Test User', 'user@host.com') == account.mock

    def test_get_or_create_account_exists2(self):
        account = mock_wrapper().with_methods(_safe_load=None)
        def query_action(name_match, email_match):
            return [account.mock] if name_match and email_match else []
        
        anchor = mock_on(Account)
        query = anchor._query
        query.action = query_action
        query.is_expected.twice() # Second attempt should succeed
        anchor.c.with_children(name='TestUser', email='user@host.com')

        assert self.importer._get_or_create_account('Test User', 'user@host.com') == account.mock

    def test_get_or_create_account_exists3(self):
        account = mock_wrapper().with_methods(_safe_load=None)
        def query_action(name_match, email_match):
            return [account.mock] if name_match and email_match else []
        
        anchor = mock_on(Account)
        query = anchor._query
        query.action = query_action
        query.is_expected.thrice() # Third attempt should succeed
        anchor.c.with_children(name='Test_User', email='user@host.com')

        assert self.importer._get_or_create_account('Test User', 'user@host.com') == account.mock

    def test_get_or_create_account_not_exists(self):
        """Should create the account if it doesn't exist"""
        account = mock_wrapper().with_methods(_safe_load=None)
        anchor = mock_on(Account)
        query = anchor._query
        query.return_value = []
        query.is_expected.thrice()

        test_user5 = mock_wrapper().with_methods(_safe_load=None)
        test_user5.name = 'Test_User5'
        
        def register_action(name, pw, email):
            if name != test_user5.name:
                raise AccountExists
            else:
                return test_user5.mock

        # Mocking on importer because it imported register
        account_module = mock_on(r2.lib.importer)
        register = account_module.register
        register.is_expected.exactly(4).times
        register.action = register_action

        created_account = self.importer._get_or_create_account('Test User', 'user@host.com')
        assert str(created_account) == 'Test_User5'

    def test_get_or_create_account_max_retries(self):
        """Should raise an error after 10 tries"""
        anchor = mock_on(Account)
        query = anchor._query.returning([]).is_expected.thrice()
        account_module = mock_on(r2.lib.importer)
        register = account_module.register.raising(AccountExists).is_expected.exactly(10).times

        self.assertRaises(
            StandardError, lambda: self.importer._get_or_create_account('Test User', 'user@host.com'),
            message='Unable to generate account after 10 retries')

    @pending
    def test_import_into_subreddit(self):
        sr = mock_wrapper()

        feed = AtomFeedFixture()
        post = feed.add_post()
        feed.add_comment(post_id=post)

        importer = AtomImporter(str(feed))
        importer.import_into_subreddit(sr)

# class TestRewitingOvercomngBiasUrls(TestCase):
#     def test_x(self):
#         