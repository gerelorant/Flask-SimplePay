import base64
import datetime as dt
import random
import json

from flask import Flask, Blueprint, abort, redirect, request, make_response, \
    jsonify
from flask_sqlalchemy import SQLAlchemy
import iso8601
import pytz

from flask_simplepay.model import TransactionMixin, OrderAddressMixin


class SimplePay(object):
    """Flask-SimplePay extension class.

    :param app: Flask application instance
    :param db: Flask-SQLAlchemy instance
    :param transaction_class: Transaction model class
    :param address_class: Order address model class

    """
    def __init__(
            self,
            app: Flask = None,
            db: SQLAlchemy = None,
            transaction_class: type(TransactionMixin) = None,
            address_class: type(OrderAddressMixin) = None
    ):
        self.app = app
        self.db = db
        self.transaction_class = transaction_class
        self.order_address_class = address_class
        self.blueprint = None

        if app is not None:
            self.init_app(app)

    def init_app(self, app: Flask):
        self.app = app
        self.app.extensions["simple_pay"] = self

        if self.transaction_class is None:
            class Transaction(self.db.Model, TransactionMixin):
                __tablename__ = "transaction"

            self.transaction_class = Transaction

        if self.order_address_class is None:
            class OrderAddress(self.db.Model, OrderAddressMixin):
                __tablename__ = "order_address"

            self.order_address_class = OrderAddress

        self.blueprint = Blueprint(
            'simple_pay',
            __name__,
            url_prefix='/simple_pay'
        )

        @self.blueprint.route('/start/<int:transaction_id>', methods=['POST'])
        def start(transaction_id: int):
            transaction = self.transaction_class.query.get(transaction_id)
            if transaction is None:
                return abort(404)

            language = request.values.get('language', None)
            customer_name = request.values.get('name', None)
            customer_email = request.values.get('email', None)

            resp = transaction.pay_with_simple(
                customer_name=customer_name,
                customer_email=customer_email,
                language=language
            )
            if 'paymentUrl' in resp:
                return redirect(resp['paymentUrl'])
            else:
                return jsonify(resp)

        @self.blueprint.route('/back')
        def back():
            response = request.args.get('r', None)
            if response is None:
                return abort(400)

            data = json.loads(base64.b64decode(response))
            transaction = self.transaction_class.query.get(data.get('o', 0))

            if transaction is None:
                return abort(404)

            event = data['e'].lower()

            transaction.result = event
            resp = transaction.back()
            self.db.session.commit()

            return resp

        @self.blueprint.route('/ipn', methods=['POST'])
        def ipn():
            addr = self.app.config.get('SIMPLE_HOST', '94.199.53.96')
            if request.remote_addr != addr:
                return abort(403)

            data = request.json
            if json is None:
                return abort(400)

            transaction = self.transaction_class.query\
                .get(data.get('orderRef'), 0)

            if transaction is None:
                return abort(404)

            transaction.method = data['method']
            transaction.status = data['status']
            finish = iso8601.parse_date(data['finishDate'])
            transaction.finish_time = finish.astimezone(pytz.timezone('utc'))

            self.db.session.commit()

            data['receiveDate'] = dt.datetime.now().astimezone().isoformat()

            data = json.dumps(data).encode('utf8')
            signature = transaction.signature(data)

            response = make_response(data)
            response.headers['Signature'] = signature
            response.headers['Content-type'] = 'application/json'
            return response

        self.app.register_blueprint(self.blueprint)

    def start_transaction(
            self,
            total: float,
            language: str,
            currency: str,
            billing_address_id: int = None,
            billing_address: OrderAddressMixin = None,
            delivery_address_id: int = None,
            delivery_address: OrderAddressMixin = None,
            merchant: str = None,
            secret_key: str = None,
            user_id: int = None,
            **kwargs
    ):
        transaction = self.transaction_class()
        transaction.id = random.randint(10**8, 10**9-1)
        transaction.total = total
        transaction.language = language
        transaction.currency = currency
        transaction.billing_address_id = billing_address_id
        transaction.delivery_address_id = delivery_address_id

        if user_id is not None:
            transaction.user_id = user_id

        for k, v in kwargs.items():
            setattr(transaction, k, v)

        self.db.session.add(transaction)
        self.db.session.commit()
        return transaction
