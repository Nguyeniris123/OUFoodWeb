import sys
sys.path.append(r"C:\ProgramData\Jenkins\.jenkins\workspace\OUFood\app")

from flask_login import logout_user, login_user, current_user, login_required
from sqlalchemy import func
from app import app, login, dao, google, admin, utils, decorators, db, momo
from flask import render_template, redirect, flash, request, url_for, session, jsonify
from datetime import datetime, timedelta
from app.vnpay import vnpay
from models import Restaurant, CuisineType, Role, Cuisine, Review, SaasPayment, Plan, Subscription, Tenant
from dao import add_user
import uuid


@app.errorhandler(401)
def error_401(error):
    return render_template("error/401.html"), 401


@app.errorhandler(403)
def error_403(error):
    return render_template("error/403.html"), 403


@app.route("/")
def home():
    keyword = request.args.get('keyword', '')
    type_filter = request.args.get('type')
    location_filter = request.args.get('location')
    cuisine_type_id = request.args.get('cuisine_type')

    query = Restaurant.query

    if keyword:
        query = query.filter(Restaurant.name.ilike(f'%{keyword}%'))
    if type_filter:
        query = query.filter(Restaurant.type == type_filter)
    if location_filter:
        query = query.filter(Restaurant.location == location_filter)
    if cuisine_type_id:
        query = query.join(Restaurant.cuisine_types).filter(CuisineType.id == cuisine_type_id)

    restaurants = query.all()

    # Tính trung bình đánh giá cho từng nhà hàng
    avg_ratings = db.session.query(
        Review.restaurant_id,
        func.avg(Review.rate).label('avg_rate')
    ).group_by(Review.restaurant_id).all()

    rating_map = {rid: round(avg, 1) for rid, avg in avg_ratings}  # Map restaurant_id -> avg_rate

    types = [r.type for r in Restaurant.query.with_entities(Restaurant.type).distinct()]
    locations = [r.location for r in Restaurant.query.with_entities(Restaurant.location).distinct()]
    cuisine_types = CuisineType.query.all()

    return render_template('index.html',
                           restaurants=restaurants,
                           types=types,
                           locations=locations,
                           cuisine_types=cuisine_types,
                           rating_map=rating_map)


@app.route('/restaurant/<int:restaurant_id>')
def restaurant_detail(restaurant_id):
    r = Restaurant.query.get_or_404(restaurant_id)

    # Lấy các cuisine từ tất cả cuisine_type liên kết
    cuisines = []
    for ct in r.cuisine_types:
        cuisines.extend(ct.cuisines)

    keyword = request.args.get('keyword', '').strip().lower()
    food_type = request.args.get('food_type')
    beverage_type = request.args.get('beverage_type')

    food_cuisines = [
        c for c in cuisines
        if c.food_type and
           (not keyword or keyword in c.name.lower()) and
           (not food_type or c.food_type.name == food_type)
    ]

    beverage_cuisines = [
        c for c in cuisines
        if c.beverage_type and
           (not keyword or keyword in c.name.lower()) and
           (not beverage_type or c.beverage_type.name == beverage_type)
    ]

    # Lấy danh sách đánh giá
    reviews = Review.query.filter_by(restaurant_id=r.id).order_by(Review.date.desc()).all()

    return render_template('restaurant_cuisine.html',
                           restaurant=r,
                           food_cuisines=food_cuisines,
                           beverage_cuisines=beverage_cuisines,
                           keyword=keyword,
                           food_type=food_type,
                           beverage_type=beverage_type,
                           reviews=reviews)


@app.route("/login", methods=['get', 'post'])
@decorators.logged_in_user
def login_process():
    if request.method.__eq__('POST'):
        username = request.form.get('username')
        password = request.form.get('password')
        u = dao.auth_user(username=username, password=password)
        if u:
            login_user(u)
            if u.role == Role.MANAGER:
                return redirect("/manager/view/order")
            else:
                next = request.args.get('next')
                return redirect(next if next else '/')
        flash("Tên đăng nhập hoặc mật khẩu không chính xác", "danger")
    return render_template('login.html')


@app.route("/login-admin", methods=['post'])
def login_admin_process():
    username = request.form.get('username')
    password = request.form.get('password')
    u = dao.auth_user(username=username, password=password)
    if u:
        login_user(u)
    else:
        flash("Đăng nhập thất bại. Vui lòng kiểm tra lại thông tin đăng nhập.", "danger")
    return redirect('/admin')


@login.user_loader
def get_user(user_id):
    return dao.get_user_by_id(user_id)


@app.route("/logout")
def logout_process():
    logout_user()
    return redirect('/login')

@app.route("/infor/restaurant", methods=['get', 'post'])
def add_infor_restaurant():
    err_msg = None
    if request.method == 'POST':
        data_restaurant = {
            'name': request.form.get('name'),
            'type': request.form.get('type'),
            'location':request.form.get('location'),
            'introduce': request.form.get('introduce'),
            'categories': request.form.getlist('categories[]'),
        }
        user_id = session.get('user_id')
        avatar = request.files.get('avatar')
        if dao.add_infor_restaurant(data_restaurant["name"], data_restaurant["type"], data_restaurant["location"], data_restaurant["introduce"], data_restaurant["categories"], user_id, avatar):
            return redirect("/login")
    return render_template('/manager/add_info_restaurant.html', err_msg=err_msg)

@app.route('/register', methods=['get', 'post'])
@decorators.logged_in_user
def register_process():
    err_msg = None
    if request.method == 'POST':
        confirm = request.form.get('confirm')
        password = request.form.get('password')
        if password == confirm:
            data = {
                'name': request.form.get('name'),
                'username': request.form.get('username'),
                'password': password,
                'email': request.form.get('email'),
                'phone': request.form.get('phone'),
                'address': request.form.get('address'),
                'role': request.form.get('role')
            }
            avatar = request.files.get('avatar')
            user_id = add_user(avatar=avatar, **data)
            session['user_id'] = user_id
            if data["role"] == "MANAGER":
                return redirect('/infor/restaurant')
            return redirect('/login')
        else:
            err_msg = 'Mật khẩu KHÔNG khớp!'

    return render_template('register.html', err_msg=err_msg)


@app.route('/login/google')
@decorators.logged_in_user
def login():
    redirect_uri = url_for('auth', _external=True)
    return google.authorize_redirect(redirect_uri)


@app.route('/auth')
@decorators.logged_in_user
def auth():
    token = google.authorize_access_token()
    user_info = google.get('userinfo').json()
    session['user'] = user_info
    print(user_info)
    if dao.get_user_by_email(user_info['email']) is None:
        add_user(name=user_info['name'], username=user_info['email'], password="123456", email=user_info['email'],
                 phone=datetime.now().strftime("%H%M%S"))

    u = dao.auth_user(username=user_info['email'], password="123456")
    if u:
        login_user(u)
        return redirect('/')
    return render_template("/register")


@app.context_processor
def common_response():
    return {
        'cart_stats': {
            'total_quantity': utils.stats_cart_quantity(session.get('cart'))
        }
    }


@app.route('/cart')
def cart():
    context = common_response()
    context['cart_stats'].update({
        'total_amount': utils.stats_cart_amount(session.get('cart'))
    })
    return render_template('cart.html', **context)


@app.route("/api/carts", methods=['post'])
def add_to_cart():
    cart = session.get('cart')
    if not cart:
        cart = {
            "order_id": str(uuid.uuid4()),
            "items": {}
        }

    id = str(request.json.get('id'))
    name = request.json.get('name')
    price = request.json.get('price')
    image = request.json.get('image')
    count = request.json.get('count')

    if id in cart['items']:
        cart['items'][id]['quantity'] = cart['items'][id]['quantity'] + 1
    else:
        cart['items'][id] = {
            "id": id,
            "name": name,
            "price": price,
            "image": image,
            "count": count,
            "quantity": 1,
            "note": ""
        }

    session['cart'] = cart
    return jsonify(utils.stats_cart_quantity(cart))


@app.route('/api/carts/<product_id>', methods=['put'])
def update_cart(product_id):
    cart = session.get('cart')
    note = request.json.get('note')
    quantity = request.json.get('quantity')

    if note is not None:
        if cart and product_id in cart['items']:
            cart['items'][product_id]['note'] = note
            session['cart'] = cart

    if quantity is not None:
        if cart and product_id in cart['items']:
            cart['items'][product_id]['quantity'] = int(quantity)
            session['cart'] = cart

    return jsonify(utils.stats_cart(cart))


@app.route('/api/carts/<product_id>', methods=['delete'])
def delete_product_in_cart(product_id):
    cart = session.get('cart')
    if cart and product_id in cart['items']:
        del cart['items'][product_id]

        if cart['items']:
            session['cart'] = cart
        else:
            session.pop('cart', None)

    return jsonify(utils.stats_cart(cart))


def get_client_ip(request):
    x_forwarded_for = request.headers.get("X-Forwarded-For")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]
    else:
        ip = request.remote_addr
    return ip


@app.route("/payment", methods=["GET", "POST"])
@login_required
def payment():
    if request.method == "GET":
        context = common_response()
        context['cart_stats'].update({
            'total_amount': utils.stats_cart_amount(session.get('cart'))
        })
        return render_template("payment.html", **context, user=current_user)
    else:
        cart = session.get('cart')

        items = list(cart['items'].values())
        validation_errors = dao.validate_cart_items(items)
        if validation_errors:
            session.pop('cart', None)
            return render_template("payment.html", title="Lỗi", result="Không thể xử lý đơn hàng",
                                   errors=validation_errors)

        receiver_name = request.form.get("person")
        receiver_phone = request.form.get("phone")
        receiver_address = request.form.get("address")

        cart = {
            **cart,
            "receiver": {
                "receiver_name": receiver_name,
                "receiver_phone": receiver_phone,
                "receiver_address": receiver_address
            }
        }
        session['cart'] = cart

        order_id = request.form.get("order_id")
        amount = float(request.form.get("amount"))
        order_type = request.form.get("order_type")
        order_desc = request.form.get("order_desc")
        bank_code = request.form.get("bank_code")
        language = request.form.get("language")
        ipaddr = get_client_ip(request)

        if request.form.get("pay") == "vnpay":
            vnp = vnpay()
            vnp.requestData["vnp_Version"] = "2.1.0"
            vnp.requestData["vnp_Command"] = "pay"
            vnp.requestData["vnp_TmnCode"] = app.config["VNPAY_TMN_CODE"]
            vnp.requestData["vnp_Amount"] = int(amount * 100)
            vnp.requestData["vnp_CurrCode"] = "VND"
            vnp.requestData["vnp_TxnRef"] = order_id
            vnp.requestData["vnp_OrderInfo"] = order_desc
            vnp.requestData["vnp_OrderType"] = order_type
            if language and language != "":
                vnp.requestData["vnp_Locale"] = language
            else:
                vnp.requestData["vnp_Locale"] = "vn"
            if bank_code and bank_code != "":
                vnp.requestData["vnp_BankCode"] = bank_code

            vnp.requestData["vnp_CreateDate"] = datetime.now().strftime("%Y%m%d%H%M%S")
            vnp.requestData["vnp_IpAddr"] = ipaddr
            vnp.requestData["vnp_ReturnUrl"] = app.config["VNPAY_RETURN_URL"]
            vnpay_payment_url = vnp.get_payment_url(
                app.config["VNPAY_PAYMENT_URL"], app.config["VNPAY_HASH_SECRET_KEY"]
            )
            return redirect(vnpay_payment_url)
        elif request.form.get("pay") == "momo":
            return redirect(momo.get_payment_url(order_id, amount))

    return redirect("/cart")


@app.route("/vnpay_payment_return", methods=["GET"])
def vnpay_payment_return():
    inputData = request.args
    if inputData:
        vnp = vnpay()
        vnp.responseData = dict(inputData)
        order_id = inputData.get("vnp_TxnRef")
        amount = int(inputData.get("vnp_Amount")) / 100
        vnp_ResponseCode = inputData.get("vnp_ResponseCode")

        if vnp.validate_response(app.config["VNPAY_HASH_SECRET_KEY"]):
            if vnp_ResponseCode == "00":
                cart = session.get('cart')

                items = list(cart['items'].values())
                receiver = cart['receiver']

                order = dao.add_order(
                    user_id=current_user.id,
                    cart_items=items,
                    receiver=receiver,
                    payment_ref=order_id
                )

                session.pop('cart', None)

                return render_template(
                    "vnpay_payment_return.html",
                    title="Thanh toán thành công",
                    result="Success",
                    order_id=order_id,
                    amount=amount,
                    vnp_ResponseCode=vnp_ResponseCode,
                )

            elif vnp_ResponseCode == "24":

                return render_template(
                    "vnpay_payment_return.html",
                    title="Hủy thanh toán",
                    result="Canceled",
                    order_id=order_id,
                    amount=amount,
                    vnp_ResponseCode=vnp_ResponseCode,
                )
            else:
                return render_template(
                    "vnpay_payment_return.html",
                    title="Lỗi thanh toán",
                    result="Error",
                    order_id=order_id,
                    amount=amount,
                    vnp_ResponseCode=vnp_ResponseCode,
                )
        else:
            return render_template(
                "vnpay_payment_return.html",
                title="Payment result",
                result="Error",
                order_id=order_id,
                amount=amount,
                vnp_ResponseCode=vnp_ResponseCode,
                msg="Invalid checksum",
            )
    return render_template(
        "vnpay_payment_return.html", title="Kết quả thanh toán", result=""
    )


@app.route("/momo_payment_return", methods=["GET"])
def momo_payment_return():
    data = request.args.to_dict()
    if data:
        order_id = data.get("orderId")
        amount = int(data.get("amount"))
        result_code = data.get("resultCode")

        if result_code == '0':
            cart = session.get('cart')

            items = list(cart['items'].values())
            receiver = cart['receiver']

            order = dao.add_order(
                user_id=current_user.id,
                cart_items=items,
                receiver=receiver,
                payment_ref=order_id
            )

            session.pop('cart', None)

            return render_template(
                "momo_payment_return.html",
                title="Thanh toán thành công",
                result="Success",
                order_id=order_id,
                amount=amount,
                result_code=result_code,
            )
        else:
            return render_template(
                "momo_payment_return.html",
                title="Lỗi thanh toán",
                result="Error",
                order_id=order_id,
                amount=amount,
                result_code=result_code,
            )
    return render_template(
        "momo_payment_return.html", title="Kết quả thanh toán", result=""
    )


@app.route("/manager/view/order")
@decorators.manager_required
def view_order():
    current_user_id = current_user.id
    orders = dao.get_order(current_user_id)
    return render_template("manager/order_accept.html", orders=orders)


@app.route("/manager/view/oder_detail/<order_id>")
@decorators.manager_required
def update_status_order(order_id):
    order_details = dao.get_order_detail(order_id)
    return render_template("manager/order_detail.html", order_details=order_details, count=len(order_details))


@app.route("/api/update/status/order", methods=['PATCH'])
@decorators.manager_required
def update_status_order_approve():
    order_id = request.json.get('order_id')
    status = request.json.get('status')
    result = dao.update_order(order_id, status)
    return jsonify({'result': result})


@app.route("/manager/cuisine/manager")
@decorators.manager_required
def view_cuisine_manager():
    cuisines = dao.get_cuisine(current_user.id)
    restaurant_id = dao.get_restaurant_id(current_user.id)
    return render_template("manager/cuisine_manager.html", cuisines=cuisines, restaurant_id=restaurant_id)


@app.route("/api/manager/delete/cuisine", methods=['DELETE'])
@decorators.manager_required
def cuisine_delete():
    cuisine_id = request.json.get("cuisine_id")
    result = dao.delete_cuisine(cuisine_id)
    print(result)
    return jsonify({"result": result})


@app.route("/manager/add/cuisine/<restaurant_id>", methods=['POST', 'GET'])
@decorators.manager_required
def cuisine_add(restaurant_id):
    err_msg = None
    cuisines_type = dao.get_cuisine_type(restaurant_id)
    print(restaurant_id[0])
    if request.method == "POST":
        cuisine_name = request.form.get("name")
        cuisine_description = request.form.get("description")
        cuisine_price = request.form.get("price")
        cuisine_type = request.form.get("cuisine_type")
        cuisine_avatar = request.files.get("cuisine_avatar")
        if cuisine_name is None or cuisine_description is None or cuisine_price is None or cuisine_type is None or cuisine_avatar is None:
            print("Hello")
            err_msg = "vui lòng điền đầy đủ thông tin món ăn"
            return render_template("manager/cuisine_add.html", cuisines_type=cuisines_type, err_msg=err_msg)
        dao.cuisine_add(cuisine_name, cuisine_price, cuisine_avatar, cuisine_description, cuisine_type)
        return redirect("/manager/cuisine/manager")
    return render_template("manager/cuisine_add.html", cuisines_type=cuisines_type, restaurant_id=restaurant_id)


@app.route("/api/update/quantity", methods=['PUT'])
@decorators.manager_required
def update_quantity_cuisine():
    cuisine_id = request.json.get('cuisine_id')
    quantity = request.json.get('quantity')
    quantity = int(quantity)
    result = dao.update_quantity(cuisine_id, quantity)
    return jsonify({'result': result})


@app.route("/manager/reputation/statistics")
@decorators.manager_required
def reputation_statistics():
    if current_user.is_authenticated:
        reviews = dao.get_review(current_user.id)
        print(reviews)
    return render_template("manager/reputation_statistics.html", reviews=reviews)


@app.route("/history")
@login_required
def history_order():
    orders = dao.get_order_history(current_user.id)
    print(orders)
    return render_template("history.html", orders=orders)


@app.route("/api/rate/restaurant", methods=["POST"])
def rate_restaurant():
    order_detail_id = request.json.get("order_detail_id")
    star = request.json.get("star")
    content = request.json.get("content")
    restaurant_id = dao.get_restaurant(order_detail_id)
    dao.add_review(restaurant_id[0], star, content, current_user.id)
    return jsonify({'result': "true"})


@app.route('/manager/packages')
def package_info():
    plan_packages = dao.get_packages()
    tenant = Tenant.query.filter_by(user_id=current_user.id).first()

    if not tenant:
        return "Không tìm thấy tenant!", 404

    subscription = Subscription.query.filter(
        Subscription.tenant_id == tenant.id,
        Subscription.status == "active",
        Subscription.end_date >= datetime.now()
    ).first()

    if not subscription:
        return render_template("manager/package/no_package.html")

    plan = subscription.plan

    return render_template(
        "packages.html",
        packages=plan_packages,
        plan=plan,
        subscription=subscription,
        now=datetime.now()
    )

MANAGER_RETURN_URL = "http://localhost:8000/manager/payment/vnpay_return"

@app.route('/manager/payment/vnpay/<int:package_id>')
@decorators.manager_required
def manager_payment_vnpay(package_id):
    # Lấy thông tin Gói và Tenant
    plan = Plan.query.get_or_404(package_id)
    tenant = Tenant.query.filter_by(user_id=current_user.id).first()

    if not tenant:
        flash("Bạn chưa đăng ký thông tin nhà hàng!", "danger")
        return redirect("/infor/restaurant")

    # Tạo Subscription ở trạng thái 'pending'
    # Tạo trước để lấy ID, nếu thanh toán thất bại thì record này sẽ giữ status pending
    new_sub = Subscription(
        tenant_id=tenant.id,
        plan_id=plan.id,
        status='pending',
        end_date=datetime.now()  # update khi thành công
    )
    db.session.add(new_sub)
    db.session.flush()  # flush để lấy new_sub.id ngay lập tức

    # Tạo mã giao dịch (TxnRef) duy nhất
    # SAAS_{subscription_id}_{timestamp} để dễ dàng truy xuất lại khi VNPay trả về
    order_id = f"SAAS_{new_sub.id}_{int(datetime.now().timestamp())}"

    # Lưu thông tin thanh toán (SaasPayment)
    new_payment = SaasPayment(
        payment_method="VNPay",
        payment_amount=plan.price,
        status=False,  # Chưa thanh toán
        subscription_id=new_sub.id
    )
    db.session.add(new_payment)
    db.session.commit()

    # Cấu hình VNPay
    vnp = vnpay()
    vnp.requestData['vnp_Version'] = '2.1.0'
    vnp.requestData['vnp_Command'] = 'pay'
    vnp.requestData['vnp_TmnCode'] = app.config['VNPAY_TMN_CODE']
    vnp.requestData['vnp_Amount'] = int(plan.price * 100)
    vnp.requestData['vnp_CurrCode'] = 'VND'
    vnp.requestData['vnp_TxnRef'] = order_id
    vnp.requestData['vnp_OrderInfo'] = f"Thanh toan goi {plan.name} cho nha hang"
    vnp.requestData['vnp_OrderType'] = 'other'
    vnp.requestData['vnp_Locale'] = 'vn'
    vnp.requestData['vnp_CreateDate'] = datetime.now().strftime('%Y%m%d%H%M%S')
    vnp.requestData['vnp_IpAddr'] = get_client_ip(request)
    vnp.requestData['vnp_ReturnUrl'] = MANAGER_RETURN_URL

    vnpay_payment_url = vnp.get_payment_url(app.config['VNPAY_PAYMENT_URL'], app.config['VNPAY_HASH_SECRET_KEY'])
    return redirect(vnpay_payment_url)


@app.route('/manager/payment/vnpay_return')
@decorators.manager_required
def manager_payment_return():
    inputData = request.args
    if inputData:
        vnp = vnpay()
        vnp.responseData = dict(inputData)

        order_id = inputData.get('vnp_TxnRef')  # SAAS_{sub_id}_{timestamp}
        amount = int(inputData.get('vnp_Amount')) / 100
        vnp_ResponseCode = inputData.get('vnp_ResponseCode')

        if vnp.validate_response(app.config['VNPAY_HASH_SECRET_KEY']):
            # Lấy subscription_id từ order_id (TxnRef)
            try:
                parts = order_id.split('_')
                if len(parts) >= 2 and parts[0] == 'SAAS':
                    sub_id = int(parts[1])
                else:
                    raise ValueError("Invalid Order ID format")
            except:
                return "Lỗi định dạng mã giao dịch", 400

            if vnp_ResponseCode == '00':
                # THANH TOÁN THÀNH CÔNG
                # Tìm Subscription và Payment
                subscription = db.session.get(Subscription, sub_id)
                payment = SaasPayment.query.filter_by(subscription_id=sub_id).first()

                if subscription and payment:
                    plan = db.session.get(Plan, subscription.plan_id)

                    # 2. Hủy các gói cũ đang active của Tenant này
                    old_active_subs = Subscription.query.filter(
                        Subscription.tenant_id == subscription.tenant_id,
                        Subscription.status == 'active',
                        Subscription.id != subscription.id
                    ).all()

                    for old_sub in old_active_subs:
                        old_sub.status = 'expired'

                    # Kích hoạt gói mới
                    subscription.status = 'active'
                    # Tính ngày hết hạn: Thời gian hiện tại + số ngày của gói
                    subscription.end_date = datetime.now() + timedelta(days=plan.time)

                    # Cập nhật trạng thái thanh toán
                    payment.status = True

                    db.session.commit()

                    flash(f"Nâng cấp gói {plan.name} thành công!", "success")
                    return redirect("/manager/packages")
            else:
                # THANH TOÁN THẤT BẠI/HỦY
                flash("Giao dịch bị hủy hoặc thất bại", "danger")
                return redirect("/manager/packages")
        else:
            return "Sai Checksum - Dữ liệu không hợp lệ"

    return redirect("/manager/packages")


if __name__ == "__main__":
    app.run(host="localhost", port=8000, debug=True)
