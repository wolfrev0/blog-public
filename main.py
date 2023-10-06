from flask import *
doc_path="docs/"
app = Flask(__name__, template_folder='static/'+doc_path)

from pygments import lexers, highlight
from pygments.formatters import HtmlFormatter
def code_renderer(code, type='Bash'):
	return highlight(code, lexers.get_lexer_by_name(type), HtmlFormatter(full=True))

menu_exclude=["all/hide"]

from os import listdir
from os.path import isfile, join, isdir

from google.cloud import datastore
import datetime

def get_datastore():
	if not get_datastore.instance:
		get_datastore.instance=datastore.Client()
	return get_datastore.instance
get_datastore.instance=None

class CategoryNode:
	def __init__(self,href="",text="",children=[]):
		self.href=href
		self.text=text
		self.children=children
def build_category_tree(path, name):
	if path in menu_exclude:
		return None
	if isfile("static/"+doc_path+path):
		return CategoryNode("/"+path, name[:-5])
	return CategoryNode("/"+path, name, filter(None.__ne__,[build_category_tree(path+"/"+i, i) for i in sorted(listdir("static/"+doc_path+path))]))

class CommentNode:
	def __init__(self,id,path,writer,text,children):
		self.id=id
		self.path=path
		self.writer=writer
		self.text=text
		self.children=children
def build_comment_tree(path):
	dc=get_datastore()
	query = dc.query(kind="comment")
	query.add_filter("path","=",path)
	res=list(query.fetch())
	res.sort(key=lambda x:x['date'])
	if not res:
		key=dc.key("comment")
		ent=datastore.Entity(key=key)
		ent['writer']='Writer'
		ent['text']='Text'
		ent['path']=path
		ent['date']=datetime.datetime.now()
		dc.put(ent)
		res=[ent]
	ch=[[] for _ in range(len(res))]
	ki=dict()
	for i,v in enumerate(res):
		ki[v.id]=i
	for i,v in enumerate(res):
		if v.key.parent:
			ch[ki[v.key.parent.id]].append(i)
		else:
			root_idx=i
	def dfs(idx):
		return CommentNode(res[idx].id,path,res[idx]['writer'],res[idx]['text'],[dfs(i) for i in ch[idx]])
	return dfs(root_idx)

from flask import request
@app.route('/comment')
def comment():
	dc=get_datastore()
	key=dc.key("comment",parent=dc.key("comment",int(request.args.get('id'))))
	ent=datastore.Entity(key=key)
	ent['writer']=request.args.get('writer')
	ent['text']=request.args.get('text')
	ent['path']=request.args.get('path')
	ent['date']=datetime.datetime.now()
	dc.put(ent)
	return redirect(request.args.get('path'))

@app.route('/')
def hello():
	dc=get_datastore()
	query = dc.query(kind="comment")
	query.order=["-date"]
	res=[i for i in query.fetch() if i.key.parent][:5]
	return render_template(
		"main.html",
		category_root=build_category_tree("all", "all"),
		article_name='Welcome!',
		recent_comments=res,
		pageview_count=pageview_trigger(0))

@app.route('/robots.txt')
def robots():
	return app.send_static_file('robots.txt')

@app.route('/ads.txt')
def ads():
	return app.send_static_file('ads.txt')

@app.route('/redirect/<keyword>')
def redirect_by_keyword(keyword):
	if not redirect_by_keyword.mapping:
		redirect_by_keyword.mapping={
			"resume":app.send_static_file('files/resume.pdf'),
			"portfolio":render_path('all/hide/Portfolio.html'),
			"portfolio-ko":render_path('all/hide/포트폴리오.html'),
		}
	return redirect_by_keyword.mapping[keyword]
redirect_by_keyword.mapping={}

@app.route('/all')
def on_all():
	return render_path('all')

@app.route('/all/<path:path>')
def on_all_path(path):
	return render_path('all/'+path)

@app.errorhandler(404)
def page404(e):
	return render_template("404.html", category_root=build_category_tree("all", "all"), article_name='ERROR 404'),404

def pageview_trigger(delta):
	datetime_today=datetime.datetime.today().replace(hour=0,minute=0,second=0,microsecond=0)

	dc=get_datastore()
	query = dc.query(kind="pageview")
	query.add_filter("date","=",datetime_today)
	pageview_count=0
	pageview_key=dc.key("pageview")
	qryres=[i for i in query.fetch()]
	if qryres:
		pageview_count=int(qryres[0]['count'])+delta
		pageview_key=qryres[0].key
	ent=datastore.Entity(key=pageview_key)
	ent['date']=datetime_today
	ent['count']=pageview_count
	dc.put(ent)
	return pageview_count

def render_path(path):
	if isfile("static/"+doc_path+path):
		print(path.split("/."))
		return render_template(
			"/"+path,
			category_root=build_category_tree("all", "all"),
			article_name=path.split("/")[-1].split(".")[-2],
			comment_tree=build_comment_tree(path),
			pageview_count=pageview_trigger(1),
			code_renderer=code_renderer)
	elif isdir("static/"+doc_path+path):
		dc=[("/"+path+"/"+i, i) for i in listdir("static/"+doc_path+path)]
		return render_template(
			"directory.html",
			category_root=build_category_tree("all", "all"),
			article_name=path.split("/")[-1],
			directory_content=dc,
			pageview_count=pageview_trigger(0),
			code_renderer=code_renderer)
	else:
		return page404(None)

if __name__ == '__main__':
	# This is used when running locally only.
	app.run(host='127.0.0.1', port=8080, debug=True)
