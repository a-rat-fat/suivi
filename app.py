import os
from datetime import datetime, date
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "dev-secret")
DB_URL = os.environ.get("DATABASE_URL", "sqlite:///hse.db")
app.config["SQLALCHEMY_DATABASE_URI"] = DB_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ----------------------- Models -----------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    initials = db.Column(db.String(8), unique=True, nullable=False)
    name = db.Column(db.String(120))
    role = db.Column(db.String(120))

class Action(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    owner = db.Column(db.String(120))
    due_date = db.Column(db.Date)
    status = db.Column(db.String(50), default="À faire")
    category = db.Column(db.String(120))  # HSE policy, Audit, Incident, etc.
    verification_result = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Risk(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    process = db.Column(db.String(200), nullable=False)
    hazard = db.Column(db.String(200), nullable=False)
    severity = db.Column(db.Integer, default=1)
    probability = db.Column(db.Integer, default=1)
    mitigation = db.Column(db.Text)
    owner = db.Column(db.String(120))
    due_date = db.Column(db.Date)
    status = db.Column(db.String(50), default="Ouvert")

    @property
    def risk_level(self):
        return (self.severity or 0) * (self.probability or 0)

class Audit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(60))  # interne, externe, fournisseur
    scope = db.Column(db.String(200))
    date = db.Column(db.Date)
    auditor = db.Column(db.String(120))
    findings = db.Column(db.Text)
    status = db.Column(db.String(50), default="Planifié")

class Incident(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date)
    location = db.Column(db.String(200))
    description = db.Column(db.Text)
    severity = db.Column(db.String(50))  # Mineur, Majeur, Critique
    root_cause = db.Column(db.Text)
    corrective_action = db.Column(db.Text)
    status = db.Column(db.String(50), default="Ouvert")

class Training(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee = db.Column(db.String(200))
    topic = db.Column(db.String(200))
    required = db.Column(db.Boolean, default=True)
    due_date = db.Column(db.Date)
    completed_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(50), default="À planifier")

class SDS(db.Model):  # Fiches de Données de Sécurité
    id = db.Column(db.Integer, primary_key=True)
    product_name = db.Column(db.String(200))
    supplier = db.Column(db.String(200))
    version = db.Column(db.String(50))
    revision_date = db.Column(db.Date)
    next_review_date = db.Column(db.Date)
    url = db.Column(db.String(500))

class Waste(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    stream = db.Column(db.String(120))  # carton, plastique, bois, DIB, etc.
    month = db.Column(db.String(7))     # YYYY-MM
    quantity_kg = db.Column(db.Float)
    action = db.Column(db.String(200))  # réduction/tri/valorisation
    status = db.Column(db.String(50), default="Suivi")

class Equipment(db.Model):  # GMAO-lite: moyens de contrôle
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200))
    asset_tag = db.Column(db.String(100))
    control_type = db.Column(db.String(120))  # vérification, étalonnage, inspection
    last_control = db.Column(db.Date)
    next_control = db.Column(db.Date)
    status = db.Column(db.String(50), default="OK")

class TeamMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200))
    role = db.Column(db.String(120))
    hire_date = db.Column(db.Date)
    status = db.Column(db.String(50), default="Actif")

class Absence(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('team_member.id'))
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    type = db.Column(db.String(80))  # CP, RTT, Maladie, etc.
    comment = db.Column(db.String(200))
    member = db.relationship('TeamMember', backref=db.backref('absences', lazy=True))

# ------------------- Helpers -------------------
def init_db():
    db.create_all()
    # Seed example user
    if User.query.count() == 0:
        db.session.add(User(initials="MZ", name="Marko Zovko", role="Resp. HSE"))
        db.session.commit()

@app.before_first_request
def _startup():
    init_db()

def get_initials():
    return session.get("initials", "")

# ------------------- Routes -------------------
@app.route("/")
def index():
    counts = {
        "actions_open": Action.query.filter(Action.status != "Clôturé").count(),
        "risks": Risk.query.count(),
        "audits": Audit.query.count(),
        "incidents_open": Incident.query.filter(Incident.status != "Clôturé").count(),
        "equip_due": Equipment.query.filter(Equipment.next_control != None).filter(Equipment.next_control <= date.today()).count(),
        "sds_due": SDS.query.filter(SDS.next_review_date != None).filter(SDS.next_review_date <= date.today()).count(),
        "train_due": Training.query.filter(Training.due_date != None).filter(Training.completed_date == None).count(),
    }
    charts = {
        "actions_by_status": _group_by(Action, Action.status),
        "waste_by_stream": _sum_by(Waste, Waste.stream, Waste.quantity_kg),
        "incidents_by_severity": _group_by(Incident, Incident.severity),
    }
    return render_template("dashboard.html", counts=counts, charts=charts, initials=get_initials())

def _group_by(model, col):
    from sqlalchemy import func
    q = db.session.query(col, func.count(model.id)).group_by(col).all()
    return [{"label": str(k or 'Non défini'), "value": v} for k, v in q]

def _sum_by(model, col, num_col):
    from sqlalchemy import func
    q = db.session.query(col, func.coalesce(func.sum(num_col), 0)).group_by(col).all()
    return [{"label": str(k or 'Non défini'), "value": float(v or 0)} for k, v in q]

# Session initials
@app.route("/set-initials", methods=["POST"])
def set_initials():
    session["initials"] = request.form.get("initials", "").strip().upper()[:6]
    flash("Initiales mises à jour.", "success")
    return redirect(request.referrer or url_for("index"))

# -------- Generic CRUD Utilities --------
def save_and_flash(msg="Enregistré."):
    db.session.commit()
    flash(msg, "success")

def parse_date(val):
    if not val: return None
    try:
        return datetime.strptime(val, "%Y-%m-%d").date()
    except:
        return None

# ----- Actions -----
@app.route("/actions")
def actions_list():
    items = Action.query.order_by(Action.due_date.asc().nulls_last()).all()
    return render_template("actions_list.html", items=items, initials=get_initials())

@app.route("/actions/new", methods=["GET", "POST"])
def actions_new():
    if request.method == "POST":
        a = Action(
            title=request.form["title"],
            description=request.form.get("description"),
            owner=request.form.get("owner"),
            due_date=parse_date(request.form.get("due_date")),
            status=request.form.get("status") or "À faire",
            category=request.form.get("category"),
            verification_result=request.form.get("verification_result"),
        )
        db.session.add(a)
        save_and_flash("Action créée.")
        return redirect(url_for("actions_list"))
    return render_template("actions_form.html", item=None, initials=get_initials())

@app.route("/actions/<int:item_id>/edit", methods=["GET", "POST"])
def actions_edit(item_id):
    item = Action.query.get_or_404(item_id)
    if request.method == "POST":
        item.title = request.form["title"]
        item.description = request.form.get("description")
        item.owner = request.form.get("owner")
        item.due_date = parse_date(request.form.get("due_date"))
        item.status = request.form.get("status")
        item.category = request.form.get("category")
        item.verification_result = request.form.get("verification_result")
        save_and_flash("Action mise à jour.")
        return redirect(url_for("actions_list"))
    return render_template("actions_form.html", item=item, initials=get_initials())

@app.route("/actions/<int:item_id>/delete", methods=["POST"])
def actions_delete(item_id):
    item = Action.query.get_or_404(item_id)
    db.session.delete(item)
    save_and_flash("Action supprimée.")
    return redirect(url_for("actions_list"))

# ----- Risks -----
@app.route("/risks")
def risks_list():
    items = Risk.query.order_by(Risk.id.desc()).all()
    return render_template("risks_list.html", items=items, initials=get_initials())

@app.route("/risks/new", methods=["GET", "POST"])
def risks_new():
    if request.method == "POST":
        r = Risk(
            process=request.form["process"],
            hazard=request.form["hazard"],
            severity=int(request.form.get("severity") or 1),
            probability=int(request.form.get("probability") or 1),
            mitigation=request.form.get("mitigation"),
            owner=request.form.get("owner"),
            due_date=parse_date(request.form.get("due_date")),
            status=request.form.get("status") or "Ouvert",
        )
        db.session.add(r)
        save_and_flash("Risque créé.")
        return redirect(url_for("risks_list"))
    return render_template("risks_form.html", item=None, initials=get_initials())

@app.route("/risks/<int:item_id>/edit", methods=["GET", "POST"])
def risks_edit(item_id):
    item = Risk.query.get_or_404(item_id)
    if request.method == "POST":
        item.process = request.form["process"]
        item.hazard = request.form["hazard"]
        item.severity = int(request.form.get("severity") or 1)
        item.probability = int(request.form.get("probability") or 1)
        item.mitigation = request.form.get("mitigation")
        item.owner = request.form.get("owner")
        item.due_date = parse_date(request.form.get("due_date"))
        item.status = request.form.get("status")
        save_and_flash("Risque mis à jour.")
        return redirect(url_for("risks_list"))
    return render_template("risks_form.html", item=item, initials=get_initials())

@app.route("/risks/<int:item_id>/delete", methods=["POST"])
def risks_delete(item_id):
    item = Risk.query.get_or_404(item_id)
    db.session.delete(item)
    save_and_flash("Risque supprimé.")
    return redirect(url_for("risks_list"))

# ----- Audits -----
@app.route("/audits")
def audits_list():
    items = Audit.query.order_by(Audit.date.desc().nulls_last()).all()
    return render_template("audits_list.html", items=items, initials=get_initials())

@app.route("/audits/new", methods=["GET", "POST"])
def audits_new():
    if request.method == "POST":
        a = Audit(
            type=request.form.get("type"),
            scope=request.form.get("scope"),
            date=parse_date(request.form.get("date")),
            auditor=request.form.get("auditor"),
            findings=request.form.get("findings"),
            status=request.form.get("status") or "Planifié",
        )
        db.session.add(a)
        save_and_flash("Audit créé.")
        return redirect(url_for("audits_list"))
    return render_template("audits_form.html", item=None, initials=get_initials())

@app.route("/audits/<int:item_id>/edit", methods=["GET", "POST"])
def audits_edit(item_id):
    item = Audit.query.get_or_404(item_id)
    if request.method == "POST":
        item.type = request.form.get("type")
        item.scope = request.form.get("scope")
        item.date = parse_date(request.form.get("date"))
        item.auditor = request.form.get("auditor")
        item.findings = request.form.get("findings")
        item.status = request.form.get("status")
        save_and_flash("Audit mis à jour.")
        return redirect(url_for("audits_list"))
    return render_template("audits_form.html", item=item, initials=get_initials())

@app.route("/audits/<int:item_id>/delete", methods=["POST"])
def audits_delete(item_id):
    item = Audit.query.get_or_404(item_id)
    db.session.delete(item)
    save_and_flash("Audit supprimé.")
    return redirect(url_for("audits_list"))

# ----- Incidents -----
@app.route("/incidents")
def incidents_list():
    items = Incident.query.order_by(Incident.date.desc().nulls_last()).all()
    return render_template("incidents_list.html", items=items, initials=get_initials())

@app.route("/incidents/new", methods=["GET", "POST"])
def incidents_new():
    if request.method == "POST":
        i = Incident(
            date=parse_date(request.form.get("date")),
            location=request.form.get("location"),
            description=request.form.get("description"),
            severity=request.form.get("severity"),
            root_cause=request.form.get("root_cause"),
            corrective_action=request.form.get("corrective_action"),
            status=request.form.get("status") or "Ouvert",
        )
        db.session.add(i)
        save_and_flash("Incident créé.")
        return redirect(url_for("incidents_list"))
    return render_template("incidents_form.html", item=None, initials=get_initials())

@app.route("/incidents/<int:item_id>/edit", methods=["GET", "POST"])
def incidents_edit(item_id):
    item = Incident.query.get_or_404(item_id)
    if request.method == "POST":
        item.date = parse_date(request.form.get("date"))
        item.location = request.form.get("location")
        item.description = request.form.get("description")
        item.severity = request.form.get("severity")
        item.root_cause = request.form.get("root_cause")
        item.corrective_action = request.form.get("corrective_action")
        item.status = request.form.get("status")
        save_and_flash("Incident mis à jour.")
        return redirect(url_for("incidents_list"))
    return render_template("incidents_form.html", item=item, initials=get_initials())

@app.route("/incidents/<int:item_id>/delete", methods=["POST"])
def incidents_delete(item_id):
    item = Incident.query.get_or_404(item_id)
    db.session.delete(item)
    save_and_flash("Incident supprimé.")
    return redirect(url_for("incidents_list"))

# ----- Training -----
@app.route("/training")
def training_list():
    items = Training.query.order_by(Training.due_date.asc().nulls_last()).all()
    return render_template("training_list.html", items=items, initials=get_initials())

@app.route("/training/new", methods=["GET", "POST"])
def training_new():
    if request.method == "POST":
        t = Training(
            employee=request.form.get("employee"),
            topic=request.form.get("topic"),
            required=True if request.form.get("required") == "on" else False,
            due_date=parse_date(request.form.get("due_date")),
            completed_date=parse_date(request.form.get("completed_date")),
            status=request.form.get("status") or "À planifier",
        )
        db.session.add(t)
        save_and_flash("Formation enregistrée.")
        return redirect(url_for("training_list"))
    return render_template("training_form.html", item=None, initials=get_initials())

@app.route("/training/<int:item_id>/edit", methods=["GET", "POST"])
def training_edit(item_id):
    item = Training.query.get_or_404(item_id)
    if request.method == "POST":
        item.employee = request.form.get("employee")
        item.topic = request.form.get("topic")
        item.required = True if request.form.get("required") == "on" else False
        item.due_date = parse_date(request.form.get("due_date"))
        item.completed_date = parse_date(request.form.get("completed_date"))
        item.status = request.form.get("status")
        save_and_flash("Formation mise à jour.")
        return redirect(url_for("training_list"))
    return render_template("training_form.html", item=item, initials=get_initials())

@app.route("/training/<int:item_id>/delete", methods=["POST"])
def training_delete(item_id):
    item = Training.query.get_or_404(item_id)
    db.session.delete(item)
    save_and_flash("Formation supprimée.")
    return redirect(url_for("training_list"))

# ----- SDS -----
@app.route("/sds")
def sds_list():
    items = SDS.query.order_by(SDS.next_review_date.asc().nulls_last()).all()
    return render_template("sds_list.html", items=items, initials=get_initials())

@app.route("/sds/new", methods=["GET", "POST"])
def sds_new():
    if request.method == "POST":
        s = SDS(
            product_name=request.form.get("product_name"),
            supplier=request.form.get("supplier"),
            version=request.form.get("version"),
            revision_date=parse_date(request.form.get("revision_date")),
            next_review_date=parse_date(request.form.get("next_review_date")),
            url=request.form.get("url"),
        )
        db.session.add(s)
        save_and_flash("FDS enregistrée.")
        return redirect(url_for("sds_list"))
    return render_template("sds_form.html", item=None, initials=get_initials())

@app.route("/sds/<int:item_id>/edit", methods=["GET", "POST"])
def sds_edit(item_id):
    item = SDS.query.get_or_404(item_id)
    if request.method == "POST":
        item.product_name = request.form.get("product_name")
        item.supplier = request.form.get("supplier")
        item.version = request.form.get("version")
        item.revision_date = parse_date(request.form.get("revision_date"))
        item.next_review_date = parse_date(request.form.get("next_review_date"))
        item.url = request.form.get("url")
        save_and_flash("FDS mise à jour.")
        return redirect(url_for("sds_list"))
    return render_template("sds_form.html", item=item, initials=get_initials())

@app.route("/sds/<int:item_id>/delete", methods=["POST"])
def sds_delete(item_id):
    item = SDS.query.get_or_404(item_id)
    db.session.delete(item)
    save_and_flash("FDS supprimée.")
    return redirect(url_for("sds_list"))

# ----- Waste -----
@app.route("/waste")
def waste_list():
    items = Waste.query.order_by(Waste.month.desc()).all()
    return render_template("waste_list.html", items=items, initials=get_initials())

@app.route("/waste/new", methods=["GET", "POST"])
def waste_new():
    if request.method == "POST":
        w = Waste(
            stream=request.form.get("stream"),
            month=request.form.get("month"),
            quantity_kg=float(request.form.get("quantity_kg") or 0),
            action=request.form.get("action"),
            status=request.form.get("status") or "Suivi",
        )
        db.session.add(w)
        save_and_flash("Flux déchets enregistré.")
        return redirect(url_for("waste_list"))
    return render_template("waste_form.html", item=None, initials=get_initials())

@app.route("/waste/<int:item_id>/edit", methods=["GET", "POST"])
def waste_edit(item_id):
    item = Waste.query.get_or_404(item_id)
    if request.method == "POST":
        item.stream = request.form.get("stream")
        item.month = request.form.get("month")
        item.quantity_kg = float(request.form.get("quantity_kg") or 0)
        item.action = request.form.get("action")
        item.status = request.form.get("status")
        save_and_flash("Flux déchets mis à jour.")
        return redirect(url_for("waste_list"))
    return render_template("waste_form.html", item=item, initials=get_initials())

@app.route("/waste/<int:item_id>/delete", methods=["POST"])
def waste_delete(item_id):
    item = Waste.query.get_or_404(item_id)
    db.session.delete(item)
    save_and_flash("Flux déchets supprimé.")
    return redirect(url_for("waste_list"))

# ----- Equipment (GMAO-lite) -----
@app.route("/equipment")
def equipment_list():
    items = Equipment.query.order_by(Equipment.next_control.asc().nulls_last()).all()
    return render_template("equipment_list.html", items=items, initials=get_initials())

@app.route("/equipment/new", methods=["GET", "POST"])
def equipment_new():
    if request.method == "POST":
        e = Equipment(
            name=request.form.get("name"),
            asset_tag=request.form.get("asset_tag"),
            control_type=request.form.get("control_type"),
            last_control=parse_date(request.form.get("last_control")),
            next_control=parse_date(request.form.get("next_control")),
            status=request.form.get("status") or "OK",
        )
        db.session.add(e)
        save_and_flash("Équipement enregistré.")
        return redirect(url_for("equipment_list"))
    return render_template("equipment_form.html", item=None, initials=get_initials())

@app.route("/equipment/<int:item_id>/edit", methods=["GET", "POST"])
def equipment_edit(item_id):
    item = Equipment.query.get_or_404(item_id)
    if request.method == "POST":
        item.name = request.form.get("name")
        item.asset_tag = request.form.get("asset_tag")
        item.control_type = request.form.get("control_type")
        item.last_control = parse_date(request.form.get("last_control"))
        item.next_control = parse_date(request.form.get("next_control"))
        item.status = request.form.get("status")
        save_and_flash("Équipement mis à jour.")
        return redirect(url_for("equipment_list"))
    return render_template("equipment_form.html", item=item, initials=get_initials())

@app.route("/equipment/<int:item_id>/delete", methods=["POST"])
def equipment_delete(item_id):
    item = Equipment.query.get_or_404(item_id)
    db.session.delete(item)
    save_and_flash("Équipement supprimé.")
    return redirect(url_for("equipment_list"))

# ----- Team & Absences -----
@app.route("/team")
def team_list():
    items = TeamMember.query.order_by(TeamMember.name.asc()).all()
    return render_template("team_list.html", items=items, initials=get_initials())

@app.route("/team/new", methods=["GET", "POST"])
def team_new():
    if request.method == "POST":
        t = TeamMember(
            name=request.form.get("name"),
            role=request.form.get("role"),
            hire_date=parse_date(request.form.get("hire_date")),
            status=request.form.get("status") or "Actif",
        )
        db.session.add(t)
        save_and_flash("Membre d'équipe ajouté.")
        return redirect(url_for("team_list"))
    return render_template("team_form.html", item=None, initials=get_initials())

@app.route("/team/<int:item_id>/edit", methods=["GET", "POST"])
def team_edit(item_id):
    item = TeamMember.query.get_or_404(item_id)
    if request.method == "POST":
        item.name = request.form.get("name")
        item.role = request.form.get("role")
        item.hire_date = parse_date(request.form.get("hire_date"))
        item.status = request.form.get("status")
        save_and_flash("Membre mis à jour.")
        return redirect(url_for("team_list"))
    return render_template("team_form.html", item=item, initials=get_initials())

@app.route("/team/<int:item_id>/delete", methods=["POST"])
def team_delete(item_id):
    item = TeamMember.query.get_or_404(item_id)
    db.session.delete(item)
    save_and_flash("Membre supprimé.")
    return redirect(url_for("team_list"))

@app.route("/absences")
def absences_list():
    items = Absence.query.order_by(Absence.start_date.desc().nulls_last()).all()
    members = TeamMember.query.order_by(TeamMember.name.asc()).all()
    return render_template("absences_list.html", items=items, members=members, initials=get_initials())

@app.route("/absences/new", methods=["GET", "POST"])
def absences_new():
    if request.method == "POST":
        a = Absence(
            member_id=int(request.form.get("member_id")),
            start_date=parse_date(request.form.get("start_date")),
            end_date=parse_date(request.form.get("end_date")),
            type=request.form.get("type"),
            comment=request.form.get("comment"),
        )
        db.session.add(a)
        save_and_flash("Absence ajoutée.")
        return redirect(url_for("absences_list"))
    members = TeamMember.query.order_by(TeamMember.name.asc()).all()
    return render_template("absences_form.html", item=None, members=members, initials=get_initials())

@app.route("/absences/<int:item_id>/edit", methods=["GET", "POST"])
def absences_edit(item_id):
    item = Absence.query.get_or_404(item_id)
    if request.method == "POST":
        item.member_id = int(request.form.get("member_id"))
        item.start_date = parse_date(request.form.get("start_date"))
        item.end_date = parse_date(request.form.get("end_date"))
        item.type = request.form.get("type")
        item.comment = request.form.get("comment")
        save_and_flash("Absence mise à jour.")
        return redirect(url_for("absences_list"))
    members = TeamMember.query.order_by(TeamMember.name.asc()).all()
    return render_template("absences_form.html", item=item, members=members, initials=get_initials())

@app.route("/absences/<int:item_id>/delete", methods=["POST"])
def absences_delete(item_id):
    item = Absence.query.get_or_404(item_id)
    db.session.delete(item)
    save_and_flash("Absence supprimée.")
    return redirect(url_for("absences_list"))

# ------------- Run -------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
