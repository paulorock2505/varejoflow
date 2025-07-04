# models.py

from extensions import db
import datetime
from werkzeug.security import generate_password_hash, check_password_hash

# === Novo model para armazenar listas de busca salvas ===
class List(db.Model):
    __tablename__ = 'lists'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.datetime.utcnow
    )

    def __repr__(self):
        return f"<List id={self.id} name={self.name}>"

class Produto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.Text)
    preco = db.Column(db.Float)
    data_criacao = db.Column(db.DateTime, default=db.func.current_timestamp())

class SavedSearch(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    search_name = db.Column(db.String(100), nullable=False)
    search_params = db.Column(db.Text, nullable=False)

class GeneratedFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    generated_date = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class AmazonProduct(db.Model):
    __tablename__ = 'amazon_product'
    id = db.Column(db.Integer, primary_key=True)
    product_type = db.Column(db.String(255), nullable=False)
    list_name = db.Column(db.String(255))
    title = db.Column(db.String(1000), nullable=False)
    brand = db.Column(db.String(255))
    currency = db.Column(db.String(10))
    price = db.Column(db.Numeric(10, 2))
    image_url = db.Column(db.String(1000))
    product_link = db.Column(db.String(1000))
    technical_details = db.Column(db.Text)
    additional_info = db.Column(db.Text)
    about_item = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    user_id = db.Column(db.Integer)

class UserList(db.Model):
    __tablename__ = 'user_list'
    __table_args__ = (
        db.UniqueConstraint("user_id", "list_name", name="uq_user_list"),
        {'extend_existing': True}
    )
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    list_name = db.Column(db.String(100), nullable=False)
    generic = db.Column(db.String(255), nullable=True)
    tag = db.Column(db.String(100), nullable=True)
    models = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    document_number = db.Column(db.String(14), unique=True, nullable=False)
    password_hash = db.Column(db.Text, nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    perm_trends = db.Column(db.Boolean, default=True)
    perm_generate_content = db.Column(db.Boolean, default=True)
    perm_amazon = db.Column(db.Boolean, default=True)

    def set_password(self, plain_password):
        self.password_hash = generate_password_hash(plain_password)

    def check_password(self, plain_password):
        return check_password_hash(self.password_hash, plain_password)

class AutomationJob(db.Model):
    __tablename__ = 'automation_jobs'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=True)
    params = db.Column(db.JSON, nullable=False)
    run_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    executed = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f"<AutomationJob id={self.id} run_at={self.run_at} executed={self.executed}>"
