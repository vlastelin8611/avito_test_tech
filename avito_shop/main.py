import os  # работаем с ос, чтобы брать переменные окружения и пути
import datetime  # для работы со временем и датами
from datetime import timedelta  # чтобы задавать интервалы времени (например, время жизни токена)
from typing import Dict, List  # для подсказок типов: dict – словарь, list – список
# fastapi – легкий веб-фреймворк, httpexception для ошибок, depends для внедрения зависимостей
from fastapi import FastAPI, HTTPException, Depends, status, Body
# oauth2passwordbearer вытаскивает токен из заголовка запроса
from fastapi.security import OAuth2PasswordBearer
# pydantic базовая модель для валидации входных/выходных данных
from pydantic import BaseModel
import jwt  # библиотека для работы с jwt-токенами (авторизация)
from jwt import PyJWTError  # ошибка, которая может возникнуть при декодировании токена
# sqlalchemy – для работы с базой через orm (отображение таблиц в классах)
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base, relationship, Session
# настройка бд
# юзаем sqlite с файлом test.db, так как испытываю временные трудности с постргрей
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")
# передаем доп. параметр, чтоб не ругалась многопоточность
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
# создаем движок подключения к базе по указанному адресу
engine = create_engine(DATABASE_URL, connect_args=connect_args)
# создаем фабрику сессий (sessionmaker) – сессия это связь с базой, через нее делаем запросы
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
# базовый класс для всех моделей – от него наследуются все таблицы
Base = declarative_base()
# модели базы данных (таблицы)

# модель юзера – таблица users, хранит инфу о юзере (имя, баланс)
class User(Base):
    __tablename__ = "users"  # имя таблицы в базе
    id = Column(Integer, primary_key=True, index=True)  # уникальный айдишник, первичный ключ, для быстрого поиска
    username = Column(String, unique=True, index=True)  # имя юзера, должно быть уникальным
    coin_balance = Column(Integer, default=1000)  # баланс монет, дефолт 1000 монет
    # список транзакций, где юзер отправлял монетки
    transfers_sent = relationship("Transaction", foreign_keys="Transaction.sender_id", back_populates="sender")
    # список транзакций, где юзер получал монетки
    transfers_received = relationship("Transaction", foreign_keys="Transaction.receiver_id", back_populates="receiver")
    # список покупок, которые сделал юзер
    purchases = relationship("Purchase", back_populates="user")

# модель транзакции – таблица transactions, хранит инфу о переводах монет
class Transaction(Base):
    __tablename__ = "transactions"  # имя таблицы

    id = Column(Integer, primary_key=True, index=True)  # ид транзакции
    sender_id = Column(Integer, ForeignKey("users.id"))  # ид отправителя (внешний ключ на таблицу users)
    receiver_id = Column(Integer, ForeignKey("users.id"))  # ид получателя
    amount = Column(Integer)  # сколько монет перевели
    # время транзакции; по умолчанию ставим текущее время (utc)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    # связь с юзером, который отправил монетки
    sender = relationship("User", foreign_keys=[sender_id], back_populates="transfers_sent")
    # связь с юзером, который получил монетки
    receiver = relationship("User", foreign_keys=[receiver_id], back_populates="transfers_received")

# модель покупки – таблица purchases, хранит инфу о покупках мерча
class Purchase(Base):
    __tablename__ = "purchases"  # имя таблицы
    id = Column(Integer, primary_key=True, index=True)  # ид покупки
    user_id = Column(Integer, ForeignKey("users.id"))  # ид юзера, который купил товар
    merch_name = Column(String)  # название купленного товара
    price = Column(Integer)  # цена, за которую купили товар
    # время покупки, ставим текущее время по умолчанию
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    # связь с юзером, который сделал покупку
    user = relationship("User", back_populates="purchases")


# перечень товаров (мерча) и их цены
# словарь, где ключ – название товара, а значение – цена в монетах
MERCH_ITEMS: Dict[str, int] = {
    "t-shirt": 80,      # футболка за 80 монет
    "cup": 20,          # кружка за 20 монет
    "book": 50,         # книжка за 50 монет
    "pen": 10,          # ручка за 10 монет
    "powerbank": 200,   # павербанк за 200 монет
    "hoody": 300,       # толстовка за 300 монет
    "umbrella": 200,    # зонт за 200 монет
    "socks": 10,        # носки за 10 монет
    "wallet": 50,       # кошелек за 50 монет
    "pink-hoody": 500   # розовая толстовка за 500 монет
}

# настройки для jwt (токенов авторизации)
# секретный ключ для подписи токенов, берем из переменной окружения или юзаем "mysecretkey"
SECRET_KEY = os.getenv("SECRET_KEY", "mysecretkey")
# алгоритм шифрования токена – юзаем hs256 (hmac с sha-256)
ALGORITHM = "HS256"
# время жизни токена, в минутах, тут 60 минут
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# функция для создания jwt токена
def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()  # копируем данные, чтоб не изменить оригинал
    if expires_delta:
        expire = datetime.datetime.utcnow() + expires_delta  # считаем время истечения, если передали интервал
    else:
        expire = datetime.datetime.utcnow() + timedelta(minutes=15)  # иначе дефолт 15 мин
    to_encode.update({"exp": expire})  # добавляем время истечения (ключ exp)
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)  # кодируем данные в токен
    return encoded_jwt  # возвращаем готовый токен

# зависимости fastapi: авторизация и работа с базой
# oauth2_scheme вытаскивает токен из заголовка "authorization" в формате "bearer <токен>"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth")

# функция для получения сессии базы данных, будет юзаться в эндпоинтах через depends
def get_db():
    db = SessionLocal()  # создаем сессию
    try:
        yield db  # отдаём сессию для использования в запросе
    finally:
        db.close()  # после запроса закрываем сессию, чтоб не висела

# функция для получения текущего юзера по токену
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    # готовим исключение, если что-то не так с токеном или юзером
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="неверные учетные данные",
        headers={"www-authenticate": "bearer"},
    )
    try:
        # декодим токен, проверяем его валидность
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")  # берем имя юзера из токена (ключ sub)
        if username is None:
            raise credentials_exception
    except PyJWTError:
        raise credentials_exception

    # ищем юзера в базе по имени
    user_obj = db.query(User).filter(User.username == username).first()
    if user_obj is None:
        raise credentials_exception
    return user_obj  # возвращаем найденного юзера

# схемы pydantic для валидации входных и выходных данных
# схема запроса для авторизации – юзер должен прислать имя и пароль
class AuthRequest(BaseModel):
    username: str  # имя юзера
    password: str  # пароль (в нашем примере пароль не проверяем)

# схема ответа для авторизации – возвращается токен
class AuthResponse(BaseModel):
    token: str  # токен для доступа к апи

# схема запроса для перевода монет – указываем кому и сколько переводим
class SendCoinRequest(BaseModel):
    toUser: str  # имя получателя
    amount: int  # количество монет для перевода

# создаем приложение fastapi
app = FastAPI(title="api avito shop", version="1.0.0")  # создаем апи с названием и версией
# событие старта – при запуске апи создаются таблицы в базе, если их еще нет

@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)  # создаем таблицы по нашим моделям

# эндпоинты (маршруты) апи
# эндпоинт авторизации (/api/auth)
# юзер отправляет имя и пароль, если юзера нет – создаем, выдаем токен
@app.post("/api/auth", response_model=AuthResponse)
def authenticate(auth: AuthRequest, db: Session = Depends(get_db)):
    user_obj = db.query(User).filter(User.username == auth.username).first()  # ищем юзера в базе
    if not user_obj:
        # если юзера нет, создаем нового с балансом 1000 монет
        user_obj = User(username=auth.username, coin_balance=1000)
        db.add(user_obj)
        db.commit()
        db.refresh(user_obj)
    # генерим токен, где в поле sub записываем имя юзера
    token = create_access_token(data={"sub": user_obj.username}, expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    return {"token": token}  # возвращаем токен

# эндпоинт перевода монет (/api/sendcoin)
@app.post("/api/sendcoin")
def send_coin(request: SendCoinRequest,
              current_user: User = Depends(get_current_user),  # получаем юзера по токену
              db: Session = Depends(get_db)):
    if request.amount <= 0:
        raise HTTPException(status_code=400, detail="сумма перевода должна быть положительной")
    # ищем получателя в базе
    recipient = db.query(User).filter(User.username == request.toUser).first()
    if not recipient:
        raise HTTPException(status_code=404, detail="пользователь-получатель не найден")
    if current_user.coin_balance < request.amount:
        raise HTTPException(status_code=400, detail="недостаточно средств")
    # уменьшаем баланс юзера (отправителя) на сумму перевода
    current_user.coin_balance -= request.amount
    # увеличиваем баланс получателя
    recipient.coin_balance += request.amount
    # создаем запись транзакции для истории перевода
    tx = Transaction(sender_id=current_user.id, receiver_id=recipient.id, amount=request.amount)
    db.add(tx)
    db.commit()
    db.refresh(current_user)
    return {"message": "монеты успешно переведены", "balance": current_user.coin_balance}

# эндпоинт покупки мерча (/api/buy/{item})
@app.get("/api/buy/{item}")
def buy_item(item: str,  # название товара передается в url
             current_user: User = Depends(get_current_user),
             db: Session = Depends(get_db)):
    merch_price = MERCH_ITEMS.get(item)  # получаем цену товара из словаря
    if merch_price is None:
        raise HTTPException(status_code=404, detail="товар не найден")
    if current_user.coin_balance < merch_price:
        raise HTTPException(status_code=400, detail="недостаточно средств для покупки")
    # уменьшаем баланс на цену товара
    current_user.coin_balance -= merch_price
    # создаем запись покупки, чтоб сохранить инфу о купленном товаре
    purchase_record = Purchase(user_id=current_user.id, merch_name=item, price=merch_price)
    db.add(purchase_record)
    db.commit()
    db.refresh(current_user)
    return {"message": f"покупка '{item}' выполнена успешно", "balance": current_user.coin_balance}

# эндпоинт получения инфы (/api/info)
@app.get("/api/info")
def api_info(current_user: User = Depends(get_current_user),
             db: Session = Depends(get_db)):
    coins = current_user.coin_balance  # берем баланс юзера
    # получаем список покупок юзера из базы
    purchases = db.query(Purchase).filter(Purchase.user_id == current_user.id).all()
    inventory = {}  # словарь для подсчета купленных товаров
    for p in purchases:
        # если товар уже есть, увеличиваем счетчик, иначе ставим 1
        inventory[p.merch_name] = inventory.get(p.merch_name, 0) + 1
    # делаем список из словаря, чтобы вернуть инфу в понятном виде
    inventory_list = [{"type": merch, "quantity": qty} for merch, qty in inventory.items()]

    # формируем историю переведенных монет: полученные и отправленные
    received = []  # список, когда юзер был получателем
    for tx in current_user.transfers_received:
        sender = db.query(User).filter(User.id == tx.sender_id).first()
        received.append({"fromUser": sender.username, "amount": tx.amount})
    sent = []  # список, когда юзер отправлял монеты
    for tx in current_user.transfers_sent:
        receiver = db.query(User).filter(User.id == tx.receiver_id).first()
        sent.append({"toUser": receiver.username, "amount": tx.amount})
    # возвращаем инфу: баланс, инвентарь (купленные товары) и историю переводов
    return {"coins": coins, "inventory": inventory_list, "coinHistory": {"received": received, "sent": sent}}
