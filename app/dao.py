import hashlib
import cloudinary.uploader
from sqlalchemy.exc import SQLAlchemyError
from datetime import  datetime, timedelta
from app import app, db

from app.models import User, Order, Payment, OrderDetail, Cuisine, OrderStatus, Restaurant, CuisineType, Review, \
    PaymentStatus, Plan, Tenant, Subscription, SaasPayment
from sqlalchemy import func, DateTime


def auth_user(username, password, role=None):
    password = str(hashlib.md5(password.encode('utf-8')).hexdigest())
    u = User.query.filter(User.username.__eq__(username),
                          User.password.__eq__(password))

    if role:
        u = u.filter(User.role.__eq__(role))

    return u.first()


def get_user_by_id(id):
    return User.query.get(id)


def add_user(name, username, password, email, phone, role, address=None, avatar=None):
    password = hashlib.md5(password.encode('utf-8')).hexdigest()

    u = User(
        name=name,
        username=username,
        password=password,
        email=email,
        phone=phone,
        address=address,
        role=role
    )

    if avatar:
        res = cloudinary.uploader.upload(avatar)
        u.avatar = res.get('secure_url')

    db.session.add(u)
    db.session.commit()
    return u.id

def get_user_by_email(email):
    return User.query.filter_by(email=email).first()


def get_order(user_id):
    return (db.session.query(
        Order.id,
        User.name,
        Order.created_date,
        Payment.total,
        Order.status,
        func.Count(OrderDetail.id).label("count")
    ).join(
        Payment, Payment.order_id == Order.id
    ).join(
        User, User.id == Order.user_id
    ).join(
        OrderDetail, OrderDetail.order_id == Order.id
    ).join(
        Cuisine, Cuisine.id == OrderDetail.cuisine_id
    ).join(
            CuisineType, CuisineType.id == Cuisine.cuisine_type_id
    ).join(
            Restaurant, Restaurant.id == CuisineType.restaurant_id
    ).filter(Restaurant.user_id == user_id)
    .group_by(Order.id,
              User.name,
                Order.created_date,
                Payment.total,
                Order.status))


def get_order_detail(order_id):
    return (
        db.session.query(
            Order.id.label("order_id"),
            Order.created_date.label("order_created_date"),
            Order.status,
            Payment.total,
            OrderDetail.note,
            OrderDetail.id.label("order_detail_id"),
            OrderDetail.quantity,
            Cuisine.id.label("cuisine_id"),
            Cuisine.name,
            Cuisine.price,
        ).join(
            Payment, Payment.order_id == Order.id
        ).join(
            OrderDetail, OrderDetail.order_id == Order.id
        ).join(
            Cuisine, Cuisine.id == OrderDetail.cuisine_id
        ).filter(Order.id == order_id)
        .order_by(OrderDetail.id).all()
    )


def update_order(order_id, status):
    order = Order.query.filter(order_id == Order.id).first()
    if order:
        if status == "Processing":
            order.status = OrderStatus.PROCESSING
        else:
            order.status = OrderStatus.COMPLETE
        db.session.commit()
        return True
    return False


def get_cuisine(user_id):
    return (
        db.session.query(
            User.id.label("user_id"),
            Restaurant.id.label("restaurant_id"),
            Restaurant.name.label("restaurant_name"),
            CuisineType.name.label("cuisine_type_name"),
            Cuisine.id.label("cuisine_id"),
            Cuisine.name.label("cuisine_name"),
            Cuisine.image,
            Cuisine.price,
            Cuisine.count
        ).join(
            Restaurant, Restaurant.user_id == User.id
        ).join(
            CuisineType, CuisineType.restaurant_id == Restaurant.id
        ).join(
            Cuisine, Cuisine.cuisine_type_id == CuisineType.id
        ).filter(User.id == user_id)
        .all()
    )


def delete_cuisine(cuisine_id):
    cuisine = Cuisine.query.filter(Cuisine.id == cuisine_id).first()
    if cuisine:
        db.session.delete(cuisine)
        db.session.commit()
        return True
    return False


def get_cuisine_type(restaurant_id):
    return (
        db.session.query(
            Restaurant.id.label("restaurant_id"),
            CuisineType.name,
            CuisineType.id.label("cuisine_type_id")
        ).join(
            CuisineType, CuisineType.restaurant_id == Restaurant.id
        ).filter(Restaurant.id == restaurant_id)
        .all()
    )


def cuisine_add(name, price, image, description, cuisine_type):
    cuisine = Cuisine(
        name=name,
        price=price,
        description=description,
        cuisine_type_id=cuisine_type
    )
    if image:
        res = cloudinary.uploader.upload(image)
        cuisine.image = res.get('secure_url')

    db.session.add(cuisine)
    db.session.commit()


def update_quantity(cuisine_id, quantity):
    cuisine = Cuisine.query.filter(Cuisine.id == cuisine_id).first()
    if cuisine:
        cuisine.count = quantity
        db.session.commit()
        return True
    return False


def get_review(user_id):
    return (
        db.session.query(
            func.date_format(Review.created_date, "%Y-%m").label('month'),
            func.avg(Review.rate).label('avg_rate')
        )
        .join(Restaurant, Restaurant.id == Review.restaurant_id)
        .join(User, User.id == Restaurant.user_id)
        .filter(User.id == user_id)
        .group_by(func.date_format(Review.created_date, "%Y-%m"))
        .order_by(func.date_format(Review.created_date, "%Y-%m"))
        .all()
    )


def add_order(user_id, cart_items, receiver, payment_ref):
    try:
        new_order = Order(
            user_id=user_id,
            status=OrderStatus.NEWORDER,
            receiver_name=receiver['receiver_name'],
            receiver_phone=receiver['receiver_phone'],
            receiver_address=receiver['receiver_address']
        )
        db.session.add(new_order)
        db.session.flush()

        total = 0

        for item in cart_items:
            cuisine = db.session.get(Cuisine, item['id'])
            quantity = item.get('quantity')
            note = item.get('note', '')

            detail = OrderDetail(
                order_id=new_order.id,
                cuisine_id=cuisine.id,
                quantity=quantity,
                note=note
            )
            db.session.add(detail)

            cuisine.count -= quantity
            total += cuisine.price * quantity

        payment = Payment(
            order_id=new_order.id,
            total=total,
            status=PaymentStatus.PAID,
            payment_ref=payment_ref
        )
        db.session.add(payment)
        db.session.commit()

        return new_order

    except SQLAlchemyError as e:
        db.session.rollback()
        raise e


def validate_cart_items(cart_items):
    errors = []
    for item in cart_items:
        cuisine = db.session.get(Cuisine, item['id'])
        if not cuisine:
            errors.append(f"Món ăn ID {item['id']} không tồn tại.")
            continue
        quantity = item.get('quantity')
        if quantity > cuisine.count:
            errors.append(f"Số lượng '{cuisine.name}' vượt quá tồn kho ({cuisine.count}).")
    return errors

def get_order_history(user_id):
    return (db.session.query(
        Order.created_date,
        Order.status,
        OrderDetail.id,
        OrderDetail.quantity,
        Cuisine.name,
        Cuisine.price
    ).join(
        User, User.id == Order.user_id
    ).join(
        OrderDetail, OrderDetail.order_id == Order.id
    ).join(
        Cuisine, Cuisine.id == OrderDetail.cuisine_id
    )
    .filter(User.id == user_id).all())

def get_restaurant(order_detail_id):
    return db.session.query(
        Restaurant.id
    ).join(
        CuisineType, CuisineType.restaurant_id == Restaurant.id
    ).join(
        Cuisine, Cuisine.cuisine_type_id == CuisineType.id
    ).join(
        OrderDetail, OrderDetail.cuisine_id == Cuisine.id
    ).filter(order_detail_id == OrderDetail.id).first()

def add_review(restaurant_id, star, content, user_id):
    review = Review(
        content = content,
        rate = star,
        date = datetime.now(),
        user_id = user_id,
        restaurant_id = restaurant_id,
        created_date=datetime.now(),
        updated_date = datetime.now()
    )
    db.session.add(review)
    db.session.commit()


def get_packages():
    return db.session.query(Plan).all()


def add_tenant(user_id, plan_id):
    tenant = db.session.query(Tenant).filter(Tenant.id == user_id).first()
    if tenant is None:
        tenant = Tenant(
            user_id=user_id,
            status=True
        )

        db.session.add(tenant)
        db.session.commit()

    subscription = db.session.query(Subscription).filter(Subscription.tenant_id == tenant.id and Subscription.end_date >= datetime.now()).first()
    print(subscription)
    if subscription:
        return -1

    number_days = db.session.query(Plan.time).filter(Plan.id == plan_id).scalar() or 0
    subscription = Subscription(
        plan_id = plan_id,
        tenant_id = tenant.id,
        end_date = datetime.now() + timedelta(days=number_days)
    )
    db.session.add(subscription)
    db.session.commit()


def add_infor_restaurant(name, type, location, introduce, categories, owner_restaurant_id, avatar):

    restaurant = Restaurant(
        name = name,
        type = type,
        location = location,
        introduce = introduce,
        user_id = owner_restaurant_id
    )

    if avatar:
        res = cloudinary.uploader.upload(avatar)
        restaurant.avatar = res.get('secure_url')

    if restaurant:

        db.session.add(restaurant)
        db.session.commit()

        for category in categories:
            cuisine_type = CuisineType(
                name=category,
                restaurant_id = restaurant.id
            )
            if cuisine_type:
                db.session.add(cuisine_type)
                db.session.commit()

        add_tenant(owner_restaurant_id, 1)
        return True

def get_restaurant_id(user_id):
    return db.session.query(Restaurant.id).filter(Restaurant.user_id == user_id).first()