import base64
import datetime as dt
import hashlib
import hmac
import json
import secrets

from flask import current_app, url_for
import flask_sqlalchemy as fsa
import requests
import sqlalchemy as sa
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import relationship, backref


class OrderAddressMixin(fsa.Model):
    __tablename__ = 'order_address'

    name = sa.Column(sa.String(80), nullable=False)
    company = sa.Column(sa.String(80), default='')
    country= sa.Column(sa.String(2), nullable=False)
    state = sa.Column(sa.String(40))
    city = sa.Column(sa.String(80))
    zip = sa.Column(sa.String(12))
    address = sa.Column(sa.String(80))
    address2 = sa.Column(sa.String(80), default='')
    phone = sa.Column(sa.String(16))

    @property
    def as_dict(self):
        return {
            'name': self.name,
            'company': self.company,
            'country': self.country,
            'state': self.state,
            'city': self.city,
            'zip': self.zip,
            'address': self.address,
            'address2': self.address2,
            'phone': self.phone
        }


class TransactionMixin(fsa.Model):
    total = sa.Column(sa.Float, nullable=False, index=True)
    language = sa.Column(sa.String(2), nullable=False)
    currency = sa.Column(
        sa.String(3),
        default=lambda: current_app.config.get('SIMPLE_CURRENCY', 'HUF'),
        nullable=False
    )

    simple_id = sa.Column(sa.String(8), unique=True, index=True)
    start_time = sa.Column(sa.DateTime)
    finish_time = sa.Column(sa.DateTime)
    ipn_received = sa.Column(sa.DateTime)
    result = sa.Column(
        sa.Enum('success', 'fail', 'timeout', 'cancel'),
        index=True
    )
    status = sa.Column(sa.String(16), index=True)
    method = sa.Column(sa.String(16), index=True)

    merchant = sa.Column(sa.String(32))
    secret_key = sa.Column(sa.String(64))

    @declared_attr
    def billing_address_id(cls):
        return sa.Column(
            sa.Integer,
            sa.ForeignKey('order_address.id')
        )

    @declared_attr
    def billing_address(cls):
        return relationship(
            'OrderAddress',
            foreign_keys=[cls.billing_address_id]
        )

    @declared_attr
    def delivery_address_id(cls):
        return sa.Column(
            sa.Integer,
            sa.ForeignKey('order_address.id')
        )

    @declared_attr
    def delivery_address(cls):
        return relationship(
            'OrderAddress',
            foreign_keys=[cls.delivery_address_id]
        )

    @declared_attr
    def user_id(cls):
        return sa.Column(
            sa.Integer,
            sa.ForeignKey('user.id')
        )

    @declared_attr
    def user(cls):
        return relationship(
            'User',
            backref=backref('transactions', lazy='dynamic')
        )

    @staticmethod
    def _salt():
        return secrets.token_urlsafe(32)

    @property
    def _merchant(self):
        if current_app.config['ENV'] == 'production':
            return self.merchant or current_app.config.get('SIMPLE_MERCHANT')
        else:
            return 'PUBLICTESTHUF'

    @property
    def _secret_key(self):
        if current_app.config['ENV'] == 'production':
            return self.secret_key or current_app.config.get('SIMPLE_KEY')
        else:
            return 'FxDa5w314kLlNseq2sKuVwaqZshZT5d6'

    def signature(self, data: bytes, secret_key: str = None):
        if secret_key is None:
            secret_key = self._secret_key
        hash_ = hmac.new(
            bytes(secret_key, 'utf8'),
            data,
            hashlib.sha384
        ).digest()
        b64 = base64.b64encode(hash_)
        return str(b64, 'utf8')

    def pay_with_simple(
            self,
            customer_name: str = None,
            customer_email: str = None,
            language: str = None
    ):
        if language is None:
            language = 'HU'

        if current_app.config.get('ENV') == 'production':
            url = 'https://api.simplepay.hu/payment/v2/start'
        else:
            url = 'https://sandbox.simplepay.hu/payment/v2/start'

        timeout_seconds = current_app.config.get('SIMPLE_TIMEOUT', 300)
        self.start_time = dt.datetime.utcnow()
        timeout_dt = dt.datetime.now() + dt.timedelta(seconds=timeout_seconds)
        timeout = timeout_dt.replace(microsecond=0).astimezone().isoformat()

        invoice = self.billing_address.as_dict \
            if self.billing_address \
            else {}
        delivery = self.delivery_address.as_dict \
            if self.delivery_address \
            else {}

        data = {
            'merchant': self._merchant,
            'orderRef': str(getattr(self, 'id')),
            'customer': customer_name or self.user.name,
            'customerEmail': customer_email or self.user.email,
            'language': getattr(self.user, 'language', None) or language,
            'currency': self.currency,
            'total': self.total,
            'salt': self._salt(),
            'methods': ['CARD'],
            'invoice': invoice,
            'delivery': delivery,
            'timeout': timeout,
            'url': url_for('simple_pay.back', _external=True),
            'sdkVersion': current_app.config.get('SIMPLE_SDK', 'v1.0')
        }

        data = json.dumps(data).encode('utf8')
        signature = self.signature(data, self.secret_key)

        resp = requests.post(
            url=url,
            data=data,
            headers={
                'Signature': signature,
                'Content-type': 'application/json'
            }
        )

        if resp.status_code == 200:
            return resp.json()
        else:
            resp.raise_for_status()

    def back(self):
        return self.result
