#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import os
import webapp2
import jinja2
import hmac
import string
import random
import json
import urllib2
from xml.dom import minidom
from google.appengine.api import memcache
from google.appengine.ext import db

SECRET ='hangjoni'

template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir), autoescape = True)

def blog_key(name = 'default'):
	return db.Key.from_path('blogs', name)

def render_str(template, **params):
	t = jinja_env.get_template(template)
	return t.render(params)

def to_json(post):
	time_fmt = '%c'
	json = {}
	json['subject'] = post.subject
	json['content'] = post.content
	json['created'] = post.created.strftime(time_fmt)
	json['last_modified'] = post.last_modified.strftime(time_fmt)
	if post.coords:
		json['coords'] = post.coords
	return json

IP_URL = 'http://api.hostip.info/?ip='
def get_coords(ip):
	url = IP_URL + ip
	content = None
	try:
		content = urllib2.urlopen(url).read()
	except URLError:
		return

	if content:
		dom = minidom.parseString(content)
		node_list = dom.getElementsByTagName('gml:coordinates')
		if node_list and node_list[0].childNodes[0].nodeValue:
			lon, lat = node_list[0].firstChild.nodeValue.split(',')
			return db.GeoPt(lat, lon)

GMAPS_URL = "http://maps.googleapis.com/maps/api/staticmap?size=380x263&sensor=false&"

def gmaps_img(points):
    ###Your code here
    url = GMAPS_URL
    for p in points:
        url = url + '&markers=%(lat)s,%(lon)s' % {'lat': p.lat, 'lon': p.lon}

class Post(db.Model):
	subject = db.StringProperty(required = True)
	content = db.TextProperty(required = True)
	created = db.DateTimeProperty(auto_now_add = True)
	last_modified = db.DateTimeProperty(auto_now = True)
	coords = db.GeoPtProperty()

	def render(self):
		self._render_text = self.content.replace('\n', '<br>')
		return render_str('post.html', post = self)

class Handler(webapp2.RequestHandler):
	def write(self, *a, **kw):
		self.response.out.write(*a, **kw)

	def render_str(self, template, **params):
		t = jinja_env.get_template(template)
		return t.render(params)

	def render(self, template, **kw):
		self.write(self.render_str(template, **kw))

	def render_json(self, d):
		json_txt = json.dumps(d)
		self.response.headers['Content-Type'] = 'application/json; charset=UTF-8'
		self.write(json_txt)

	def set_cookie(self, uid):
		self.response.headers['Content-Type'] = 'text/plain'
		cookie = make_secure_val(uid)
		self.response.headers.add_header('Set-Cookie', "uid=%s" % str(cookie), path = '/')

	def clear_cookie(self):
		self.response.delete_cookie('uid', path='/')

def top_posts(update = False):
	key = 'top'
	contents = memcache.get(key)
	if not update and contents:
		return contents
	else:
		contents = db.GqlQuery("SELECT * FROM Post ORDER BY created DESC")
		#contents = Post.all().order('-created')

		contents = list(contents)
		memcache.set(key, contents)
		return contents


class MainHandler(Handler):
	def get(self):
		contents = top_posts()
		points = []
		points = filter(None, (c.coords for c in contents))
		
		if points:
			img_url = gmaps_img(points)
		else:
			img_url = None
		
		self.render("front.html", contents = contents, img_url = img_url)

class PostPage(Handler):
	def get(self, post_id):
		key = db.Key.from_path('Post', int(post_id), parent = blog_key())
		post = db.get(key)

		if not post:
			self.error(404)
			return

		top_posts(TRUE)
		self.render("permalink.html", post = post)

class NewPost(Handler):
	def get(self):
		self.render("new_post.html")

	def post(self):
		subject = self.request.get("subject")
		content = self.request.get("content")
		
		if subject and content:
			p = Post(parent = blog_key(), subject = subject, content = content)
			coords = get_coords(self.request.remote_addr)
			if coords:
				p.coords = coords
			
			p.put()
			self.redirect('/blog/%s' % str(p.key().id()))

		else:
			error = "we need both a subject and some content!"
			self.render('new_post.html', subject=subject, content=content, error=error)

# Setting Up Users
class User(db.Model):
	uid = db.StringProperty(required = True)
	password = db.StringProperty(required = True)

class RegistrationHandler(Handler):
	def get(self):
		self.render("registration.html")

	def post(self):
		uid = self.request.get('uid')
		password_1 = self.request.get('password_1')
		password_2 = self.request.get('password_2')

		error_uid = error_password_1 = error_password_2 = ""

		if not uid:
			error_uid = "Please choose your username"

		if not password_1:
			error_password_1 = "Please choose a password"

		if not password_2:
			error_password_2 = "Please retype your password"
		elif password_2 != password_1:
			error_password_2 = "Please make sure you retype your password correctly"

		if error_uid != "" or error_password_1 != "" or error_password_2 != "":
			self.render('registration.html', error_uid = error_uid, error_password_1 = error_password_1, error_password_2 = error_password_2)
		else:
			u = User(uid = uid, password = encode_password(password_1))
			u.put()
			self.set_cookie(uid)
			self.redirect('/welcome')

class WelcomeHandler(Handler):
	def get(self):
		
		cookie = self.request.cookies.get('uid', None)
		uid = check_secure_val(cookie)
		if uid:
			self.write('Welcome, %s' % uid)
		else:
			self.redirect('/registration')

#make secure cookie
def hash_str(s):
	return hmac.new(SECRET, s).hexdigest()

def make_secure_val(s):
	return "%s|%s" % (s, hash_str(s))

def check_secure_val(h):
	if not h:
		return False
	else:
		val = h.split('|')[0]
		if h == make_secure_val(val):
			return val

#secure password
def make_salt():
	letters = string.ascii_letters + string.digits
	n = len(letters)
	salt = ''.join(letters[random.randrange(0, n - 1)] for x in xrange(5))
	return salt

def encode_password(password, salt = None):
	if not salt: 
		salt = make_salt()
	encoded_password = hmac.new(str(salt), str(password)).hexdigest()
	return '%s|%s' %(salt, encoded_password)

def check_password(password, encoded_password):
	if not encoded_password:
		return False
	else:
		salt = encoded_password.split('|')[0]
		return encode_password(password, salt) == encoded_password

class LoginHandler(Handler):
	def get(self):
		self.render('login.html')

	def post(self):
		uid = self.request.get('uid')
		password = self.request.get('password')
		user = db.GqlQuery('SELECT * FROM User where uid = \'%s\'' % uid).get()

		if user:
			if check_password(password, user.password):
				self.set_cookie(uid)
				self.redirect('/welcome')
			else:
				self.render('login.html', uid = uid, error = 'Incorrect password. Try again!')
		else:
			self.render('login.html', uid = uid, error = 'Username does not exist. Try again or register')

class LogoutHandler(Handler):
	def get(self):
		self.clear_cookie()
		self.redirect('/login')
	
class MainJson(MainHandler):
	def get(self):
		contents = db.GqlQuery("SELECT * FROM Post ORDER BY created DESC")

		posts = []
		for p in contents:
			posts.append(p)
		
		if len(posts) == 0:
			self.render_json({'status': 'no results to display'})
		else:
			r = [to_json(post) for post in posts]
			self.render_json(r)

class PostPageJson(MainHandler):	

	def get(self,post_id):
		key = db.Key.from_path('Post', int(post_id), parent = blog_key())
		post = db.get(key)

		if not post:
			self.error(404)
			return

		self.render_json(to_json(post))


app = webapp2.WSGIApplication([
    ('/', MainHandler),
    ('/.json', MainJson),
    ('/blog', NewPost),
    ('/blog/([0-9]+)', PostPage),
    ('/blog/([0-9]+)/.json', PostPageJson),
    ('/registration', RegistrationHandler),
    ('/welcome', WelcomeHandler),
    ('/login', LoginHandler),
    ('/logout', LogoutHandler),
], debug=True)
