from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import and_
from fastapi.security import OAuth2PasswordRequestForm
from . import models, database
import jwt
from datetime import datetime, timedelta
import hashlib
from fastapi import Response
from fastapi_login import LoginManager
from jwt.exceptions import InvalidTokenError
from urllib.parse import urlencode
from fastapi import Form
from typing import Optional
import telebot
from .settings import token, SECRET_KEY, ALGORITHM


bot = telebot.TeleBot(token)
app = FastAPI()
templates = Jinja2Templates(directory="app/templates")
manager = LoginManager(SECRET_KEY, token_url='/login', use_cookie=True)
error_type = {
    '1': 'Вы не вошли в аккаунт, войдете пожалуйста в аккаунт',
    '2': 'Ваш сеанс закончен, войдите еще раз',
    '3': 'Введен неправильно логин или пароль'
}
list_status_edit = ['Открыт', 'В работе', 'Закрыт']


def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


def verify_password(plain_password, hashed_password):
    return get_password_hash(plain_password) == hashed_password


def get_password_hash(password):
    test = password.encode()
    return hashlib.sha256(test).hexdigest()


def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def authenticate_user(db: Session, username: str, password: str):
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user


def check_session(token):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except InvalidTokenError:
        params = urlencode({'error':2})
        return RedirectResponse(url=f'/login?{params}')


@manager.user_loader()
def load_user(username: str):
    db = database.SessionLocal()
    user = db.query(models.User).filter(models.User.username == username).first()
    if user:
        return user


@app.middleware('http')
async def validate_token(request: Request, call_next):
    if request.url.path != '/login' and request.url.path != '/register':
        if 'access-token' in request.cookies:
            token = request.cookies['access-token']
        else:
            params = urlencode({'error':1})
            return RedirectResponse(url=f'/login?{params}')
        if check_session(token):
            return check_session(token)
    response = await call_next(request)
    return response


@app.get('/login', response_class=HTMLResponse)
def login(request: Request):
    error = ''
    error_param = request.query_params.get('error')
    if "access-token" in request.cookies and not check_session(request.cookies['access-token']):
        return RedirectResponse(url='/dashboard')
    if error_param:
        error = error_type[error_param]
    return templates.TemplateResponse('login.html', {'request': request, 'error': error})


@app.get('/dashboard')
@app.post('/dashboard')
def dashboard(request: Request, db: Session = Depends(get_db), dropdown_status: Optional[str] = Form(None), dropdown_app: Optional[str] = Form(None)):
    list_status= list(map(lambda x: x[0], db.query(models.Tickets.status).distinct().all()))
    list_status.insert(0, 'Все')
    list_app= list(map(lambda x: x[0], db.query(models.Tickets.applicant_name).distinct().all()))
    list_app.insert(0, 'Все')
    tickets = db.query(models.Tickets).all()
    if dropdown_status and dropdown_app and dropdown_app != 'Все' and dropdown_status != 'Все':
        tickets = db.query(models.Tickets).filter(and_(models.Tickets.status == dropdown_status, models.Tickets.applicant_name == dropdown_app)).all()
    elif dropdown_app == 'Все' and dropdown_status == 'Все':
        tickets = db.query(models.Tickets).all()
    elif dropdown_status and dropdown_app == 'Все':
        tickets = db.query(models.Tickets).filter(models.Tickets.status == dropdown_status)
    elif dropdown_app and dropdown_status == 'Все':
        tickets = db.query(models.Tickets).filter(models.Tickets.applicant_name == dropdown_app)
    return templates.TemplateResponse('main.html', {'request': request, 'tickets': tickets, 'list_status': list_status, 'list_app': list_app})


@app.post("/login")
def login(request: Request,response: Response, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        return templates.TemplateResponse('login.html', {'request': request, 'error': error_type['3']})
    token = manager.create_access_token(
        data=dict(sub=user.username),
        expires = timedelta(days=2,
                            seconds=60)
    )
    response = RedirectResponse(url='/dashboard')
    manager.set_cookie(response, token)
    return response


@app.get("/edit")
def edit(request: Request, id: str, db: Session = Depends(get_db)):
    data = db.query(models.Tickets).get(id)
    list_employee = list(map(lambda x: x[0], db.query(models.User.username).distinct().all()))
    return templates.TemplateResponse('edit.html',
                                      {
                                          'request': request,
                                          'data': data,
                                          'list_status': list_status_edit,
                                          'list_employee': list_employee})


@app.post('/edit')
def edit(db: Session = Depends(get_db),
         dropdown_edit: str = Form(...),
         answer: str = Form(None),
         dropdown_employee: str = Form(None),
         id: str = Form(...)):
    if dropdown_employee == 'null':
        dropdown_employee = None
    db.query(models.Tickets).filter(models.Tickets.id == id).update(
        {
            models.Tickets.status: dropdown_edit,
            models.Tickets.date_update: datetime.now(),
            models.Tickets.employee: dropdown_employee
        },
        synchronize_session=False)
    db.commit()
    if db.query(models.Tickets).get(id).status == 'Закрыт':
        bot.send_message(db.query(models.Tickets).get(id).applicant_id,
                         'Ваша проблема решена, если хотите еще раз обратиться, напишите текст обращения')
    if answer:
        db.query(models.Tickets).filter(models.Tickets.id == id).update(
        {
            models.Tickets.message_send: answer,
            models.Tickets.message_answer: None
        },
        synchronize_session=False)
        db.commit()
        bot.send_message(db.query(models.Tickets).get(id).applicant_id, f'Сообщение от поддержки:\n{answer}')
    return RedirectResponse(url='/dashboard')

@app.get('/register', response_class=HTMLResponse)
def register_form(request: Request):
    return templates.TemplateResponse('register.html', {'request': request})


@app.post('/register')
def register(username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    hashed_password = get_password_hash(password)
    db_user = models.User(username=username, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return RedirectResponse(url='/login')


@app.get('/logout')
def logout(response: Response):
    response = RedirectResponse(url='/login')
    response.delete_cookie("access-token")
    return response


@app.get('/')
def read_root():
    return RedirectResponse(url='/dashboard')
