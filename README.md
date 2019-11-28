# Flask-SimplePay

OTP SimplePay integration with Flask

## Usage
Initialize the extension with Flask and Flask-SQLAlchemy instances.
```python
from flask import Flask
from flask_simplepay import SimplePay
from flask_sqlalchemy import SQLAlchemy


app = Flask(__name__)
db = SQLAlchemy(app)
translations = SimplePay(app, db)
    

if __name__ == '__main__':
    app.run()
```
To start payment, a `Transaction` is needed. After adding the transaction and 
commiting the session, the `/simple/start/<int:transaction_id>` endpoint starts
the payment procedure. When the payment process is finished, the `/simple/back`
endpoint is called. To define what behaviour, extend the `TransactionMixin` 
class and override the `back()` method. Return value should be anything a Flask
route method would return.
```python
from flask import render_template
from flask_simplepay import TransactionMixin


class Transaction(db.Model, TransactionMixin):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    
    def back(self):
        return render_template({self.result}, transaction=self)
```
The `Transaction` method should be provided at initialization as
`transaction_class` argument.