import sys
from sqlalchemy import Column, ForeignKey, Integer, String, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy import create_engine

from markdown import markdown
from markdown.extensions.codehilite import CodeHiliteExtension
from markdown.extensions.extra import ExtraExtension
from micawber import bootstrap_basic, parse_html
from micawber.cache import Cache as OEmbedCache

Base = declarative_base()

oembed_providers = bootstrap_basic(OEmbedCache())

class Entry(Base):
	__tablename__ = 'entry'
	title = Column(String, nullable=False)
	content = Column(String, nullable=False)
	published = Column(Boolean)
	timestamp = Column(DateTime)
	slug = Column(String)
	id = Column(Integer, primary_key = True)

	@property
	def html_content(self):
		hilite = CodeHiliteExtension(linenums=False, css_class='highlight')
		extras = ExtraExtension()
		markdown_content = markdown(self.content, extensions=[hilite, extras])
		oembed_content = parse_html(
			markdown_content,
			oembed_providers,
			urlize_all=True,
			maxwidth=app.config['SITE_WIDTH'])
		return Markup(oembed_content)
	

# class FTSEntry(FTSModel):
# 	__tablename__ = 'ftsentry'
# 	entry_id = Column(Integer)
# 	content = Column(String)
# 	id = Column(Integer, primary_key = True)


engine = create_engine('sqlite:///blog.db')
Base.metadata.create_all(engine)