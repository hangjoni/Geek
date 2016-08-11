import sys
from flask import Markup, Flask, render_template, url_for, request, redirect, flash

from sqlalchemy import Column, ForeignKey, Integer, String, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime

from markdown import markdown
from markdown.extensions.codehilite import CodeHiliteExtension
from markdown.extensions.extra import ExtraExtension
from micawber import bootstrap_basic, parse_html
from micawber.cache import Cache as OEmbedCache

app = Flask(__name__)
SITE_WIDTH = 800

############

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
			urlize_all=True)
		return Markup(oembed_content)
	

# class FTSEntry(FTSModel):
# 	__tablename__ = 'ftsentry'
# 	entry_id = Column(Integer)
# 	content = Column(String)
# 	id = Column(Integer, primary_key = True)


engine = create_engine('sqlite:///blog.db')
Base.metadata.create_all(engine)

######################

engine = create_engine('sqlite:///blog.db')
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)
session = DBSession()

@app.route('/')
@app.route('/home')
@app.route('/index')
def index():
	posts = session.query(Entry).filter_by(published=True).all()
	return render_template('home.html', posts = posts)

@app.route('/view/<int:entry_id>')
def viewEntry(entry_id):
	post = session.query(Entry).filter_by(id=entry_id).one()
	if post:
		return render_template('viewentry.html', post = post)
	return 'Entry not found'


@app.route('/compose', methods=['GET', 'POST'])
def compose():
	if request.method == 'POST':
		newEntry = Entry(title=request.form['title'], 
			content=request.form['content'], 
			published=True,
			timestamp = datetime.utcnow(),
			slug = '')
		session.add(newEntry)
		session.commit()
		flash ('new blog entry added')
		return redirect(url_for('viewEntry', entry_id = newEntry.id))	
	return render_template('newentry.html')


@app.route('/edit/<int:entry_id>', methods = ['GET', 'POST'])
def editEntry(entry_id):
	post = session.query(Entry).filter_by(id=entry_id).one()
	if request.method == 'POST':
		post.title = request.form['title']
		post.content = request.form['content']
		timestamp = datetime.utcnow()
		session.add(post)
		session.commit()
		flash('blog post edited!')
		return redirect(url_for('viewEntry', entry_id = post.id))
	return render_template('editentry.html', post=post)


@app.route('/drafts')
def allDrafts():
	return 'View all Draft Entries'


@app.route('/draft/<int:entry_id>')
def draft(entry_id):
	return 'View Draft with entry_id: %d' % entry_id


@app.route('/delete/<int:entry_id>', methods = ['GET', 'POST'])
def deleteEntry(entry_id):
	post = session.query(Entry).filter_by(id=entry_id).one()
	if request.method == 'POST':
		session.delete(post)
		session.commit()
		flash('blog post deleted')
		return redirect(url_for('index'))
	elif request.method == 'GET':
		return render_template('deleteentry.html', post=post)
	else:
		return 'some unknown method'

@app.route('/search/<string:q>')
def search(q):
	return 'Seaerch results'


if __name__ == '__main__':
	app.secret_key = 'super secret key'
	app.debug = True
	app.run(host='0.0.0.0', port=5000)