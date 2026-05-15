from flask import Flask, render_template, request, redirect, url_for, session, flash
from config import get_connection, ADMIN_USERNAME, ADMIN_PASSWORD
from werkzeug.security import generate_password_hash, check_password_hash
import functools

app = Flask(__name__)
app.secret_key = 'gestion_cotisations_secret_key'

# ─── Décorateurs de protection ────────────────────────────────────────────────
def login_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def gestionnaire_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        if session.get('role') != 'gestionnaire':
            return redirect(url_for('espace_membre'))
        return f(*args, **kwargs)
    return decorated_function



from flask import Flask, render_template, request, redirect, url_for, session, flash
from config import get_connection, ADMIN_USERNAME, ADMIN_PASSWORD
from werkzeug.security import generate_password_hash, check_password_hash
import functools

app = Flask(__name__)
app.secret_key = 'gestion_cotisations_secret_key'

# ─── Route Login ──────────────────────────────────────────────────────────────
@app.route('/login', methods=['GET', 'POST'])
def login():
    erreur = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Vérifier si c'est le gestionnaire
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['logged_in'] = True
            session['role']      = 'gestionnaire'
            session['username']  = username
            return redirect(url_for('dashboard'))

        # Vérifier si c'est un membre
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute("""
            SELECT id, nom, prenom, role 
            FROM membres 
            WHERE email = %s AND mot_de_passe = %s
        """, (username, password))
        membre = cur.fetchone()
        cur.close()
        conn.close()

        if membre:
            session['logged_in']  = True
            session['role']       = membre[3]
            session['membre_id']  = membre[0]
            session['username']   = f"{membre[1]} {membre[2]}"
            return redirect(url_for('espace_membre'))
        else:
            erreur = "Identifiants incorrects. Réessayez."

    return render_template('login.html', erreur=erreur)

# ─── Route Logout ─────────────────────────────────────────────────────────────
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ─── Route 1 : Tableau de bord ───────────────────────────────────────────────
@app.route('/')
@gestionnaire_required
def dashboard():
    conn = get_connection()
    cur  = conn.cursor()

    cur.execute("SELECT SUM(montant_paye) FROM paiements")
    total_collecte = cur.fetchone()[0] or 0

    cur.execute("SELECT COUNT(*) FROM paiements WHERE statut = 'impayé'")
    nb_impayes = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM membres")
    nb_membres = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM penalites WHERE statut = 'impayée'")
    nb_penalites = cur.fetchone()[0]

    cur.execute("""
        SELECT 
            p.libelle,
            p.montant_attendu * COUNT(m.id) AS total_attendu,
            SUM(pa.montant_paye)            AS total_collecte
        FROM paiements pa
        JOIN membres  m ON pa.membre_id  = m.id
        JOIN periodes p ON pa.periode_id = p.id
        GROUP BY p.id, p.libelle, p.montant_attendu
        ORDER BY p.date_debut
    """)
    stats_periodes = cur.fetchall()

    cur.execute("""
        SELECT statut, COUNT(*) 
        FROM paiements 
        GROUP BY statut
    """)
    stats_statuts = cur.fetchall()

    cur.close()
    conn.close()

    return render_template('dashboard.html',
        total_collecte  = total_collecte,
        nb_impayes      = nb_impayes,
        nb_membres      = nb_membres,
        nb_penalites    = nb_penalites,
        stats_periodes  = stats_periodes,
        stats_statuts   = stats_statuts
    )
    

# ─── Route 2 : Liste des membres ─────────────────────────────────────────────
@app.route('/membres')
@gestionnaire_required
def liste_membres():
    conn = get_connection()
    cur  = conn.cursor()

    cur.execute("""
        SELECT 
            id, nom, prenom, sexe,
            EXTRACT(YEAR FROM AGE(date_naissance)) AS age,
            lieu_residence, telephone, date_adhesion, email
        FROM membres
        ORDER BY nom
    """)
    membres = cur.fetchall()

    cur.close()
    conn.close()

    return render_template('membres.html', membres=membres)

# ─── Route 3 : Ajouter un membre ─────────────────────────────────────────────
@app.route('/membres/ajouter', methods=['GET', 'POST'])
@gestionnaire_required
def ajouter_membre():
    if request.method == 'POST':
        nom            = request.form['nom']
        prenom         = request.form['prenom']
        sexe           = request.form['sexe']
        date_naissance = request.form['date_naissance']
        lieu_residence = request.form['lieu_residence']
        telephone      = request.form['telephone']
        email          = request.form['email']
        mot_de_passe   = request.form['mot_de_passe']

        conn = get_connection()
        cur  = conn.cursor()

        cur.execute("""
            INSERT INTO membres 
                (nom, prenom, sexe, date_naissance, lieu_residence, 
                 telephone, email, mot_de_passe, role)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'membre')
        """, (nom, prenom, sexe, date_naissance, lieu_residence,
              telephone, email, mot_de_passe))

        conn.commit()
        cur.close()
        conn.close()

        return redirect(url_for('liste_membres'))

    return render_template('ajouter_membre.html')
# ─── Route 4 : Liste des paiements ───────────────────────────────────────────
@app.route('/paiements')
@gestionnaire_required
def liste_paiements():
    conn = get_connection()
    cur  = conn.cursor()

    cur.execute("""
        SELECT 
            m.nom, m.prenom, p.libelle,
            pa.montant_paye, pa.date_paiement, pa.statut
        FROM paiements pa
        JOIN membres  m ON pa.membre_id  = m.id
        JOIN periodes p ON pa.periode_id = p.id
        ORDER BY p.date_debut, m.nom
    """)
    paiements = cur.fetchall()

    cur.close()
    conn.close()

    return render_template('paiements.html', paiements=paiements)

# ─── Route 5 : Statistiques de la caisse ─────────────────────────────────────
@app.route('/caisse')
@gestionnaire_required
def caisse():
    conn = get_connection()
    cur  = conn.cursor()

    cur.execute("""
        SELECT 
            p.libelle,
            p.montant_attendu * COUNT(m.id)      AS total_attendu,
            SUM(pa.montant_paye)                 AS total_collecte,
            p.montant_attendu * COUNT(m.id) 
                - SUM(pa.montant_paye)           AS manque_a_gagner
        FROM paiements pa
        JOIN membres  m ON pa.membre_id  = m.id
        JOIN periodes p ON pa.periode_id = p.id
        GROUP BY p.id, p.libelle, p.montant_attendu
        ORDER BY p.date_debut
    """)
    stats = cur.fetchall()

    cur.close()
    conn.close()

    return render_template('caisse.html', stats=stats)

# ─── Lancement ────────────────────────────────────────────────────────────────
# ─── Route 6 : Ajouter un paiement ───────────────────────────────────────────
@app.route('/paiements/ajouter', methods=['GET', 'POST'])
@gestionnaire_required
def ajouter_paiement():
    conn = get_connection()
    cur  = conn.cursor()

    if request.method == 'POST':
        membre_id     = request.form['membre_id']
        periode_id    = request.form['periode_id']
        montant_paye  = request.form['montant_paye']
        date_paiement = request.form['date_paiement']
        statut        = request.form['statut']

        cur.execute("""
            INSERT INTO paiements 
                (membre_id, periode_id, montant_paye, date_paiement, statut)
            VALUES (%s, %s, %s, %s, %s)
        """, (membre_id, periode_id, montant_paye, date_paiement, statut))

        conn.commit()
        cur.close()
        conn.close()

        return redirect(url_for('liste_paiements'))

    # Récupérer les membres et périodes pour les listes déroulantes
    cur.execute("SELECT id, nom, prenom FROM membres ORDER BY nom")
    membres = cur.fetchall()

    cur.execute("SELECT id, libelle FROM periodes ORDER BY date_debut")
    periodes = cur.fetchall()

    cur.close()
    conn.close()

    return render_template('ajouter_paiement.html',
        membres  = membres,
        periodes = periodes
    )

# ─── Route 7 : Ajouter une pénalité ──────────────────────────────────────────
@app.route('/penalites/ajouter', methods=['GET', 'POST'])
@gestionnaire_required
def ajouter_penalite():
    conn = get_connection()
    cur  = conn.cursor()

    if request.method == 'POST':
        membre_id        = request.form['membre_id']
        periode_id       = request.form['periode_id']
        montant_penalite = request.form['montant_penalite']
        motif            = request.form['motif']
        date_application = request.form['date_application']
        statut           = request.form['statut']

        cur.execute("""
            INSERT INTO penalites 
                (membre_id, periode_id, montant_penalite, motif, date_application, statut)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (membre_id, periode_id, montant_penalite, motif, date_application, statut))

        conn.commit()
        cur.close()
        conn.close()

        return redirect(url_for('liste_penalites'))

    cur.execute("SELECT id, nom, prenom FROM membres ORDER BY nom")
    membres = cur.fetchall()

    cur.execute("SELECT id, libelle FROM periodes ORDER BY date_debut")
    periodes = cur.fetchall()

    cur.close()
    conn.close()

    return render_template('ajouter_penalite.html',
        membres  = membres,
        periodes = periodes
    )

# ─── Route 8 : Liste des pénalités ───────────────────────────────────────────
@app.route('/penalites')
@gestionnaire_required
def liste_penalites():
    conn = get_connection()
    cur  = conn.cursor()

    cur.execute("""
        SELECT 
            m.nom, m.prenom, p.libelle,
            pe.montant_penalite, pe.motif,
            pe.date_application, pe.statut
        FROM penalites pe
        JOIN membres  m ON pe.membre_id  = m.id
        JOIN periodes p ON pe.periode_id = p.id
        ORDER BY pe.date_application DESC
    """)
    penalites = cur.fetchall()

    cur.close()
    conn.close()

    return render_template('penalites.html', penalites=penalites)
# ─── Route 9 : Générer les pénalités automatiquement ─────────────────────────
@app.route('/penalites/generer', methods=['POST'])
@gestionnaire_required
def generer_penalites():
    conn = get_connection()
    cur  = conn.cursor()

    # On cherche tous les paiements impayés ou partiels
    cur.execute("""
        SELECT pa.membre_id, pa.periode_id, pa.statut
        FROM paiements pa
        WHERE pa.statut IN ('impayé', 'partiel')
    """)
    paiements_a_penaliser = cur.fetchall()

    nb_generes = 0  # compteur de pénalités générées

    for p in paiements_a_penaliser:
        membre_id  = p[0]
        periode_id = p[1]
        statut     = p[2]

        # Vérifier si une pénalité existe déjà pour ce membre et cette période
        cur.execute("""
            SELECT COUNT(*) FROM penalites
            WHERE membre_id = %s AND periode_id = %s
        """, (membre_id, periode_id))
        existe = cur.fetchone()[0]

        # On ne génère que si elle n'existe pas encore
        if existe == 0:
            if statut == 'impayé':
                montant = 1000.00
                motif   = 'Retard de paiement'
            else:
                montant = 500.00
                motif   = 'Paiement partiel'

            cur.execute("""
                INSERT INTO penalites 
                    (membre_id, periode_id, montant_penalite, motif, date_application, statut)
                VALUES (%s, %s, %s, %s, CURRENT_DATE, 'impayée')
            """, (membre_id, periode_id, montant, motif))

            nb_generes += 1

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for('liste_penalites'))

# ─── Route 10 : Modifier un membre ───────────────────────────────────────────
@app.route('/membres/modifier/<int:id>', methods=['GET', 'POST'])
@gestionnaire_required
def modifier_membre(id):
    conn = get_connection()
    cur  = conn.cursor()

    if request.method == 'POST':
        nom            = request.form['nom']
        prenom         = request.form['prenom']
        sexe           = request.form['sexe']
        date_naissance = request.form['date_naissance']
        lieu_residence = request.form['lieu_residence']
        telephone      = request.form['telephone']
        email          = request.form['email']
        mot_de_passe   = request.form['mot_de_passe']

        if mot_de_passe:
            cur.execute("""
                UPDATE membres
                SET nom=%s, prenom=%s, sexe=%s, date_naissance=%s,
                    lieu_residence=%s, telephone=%s, email=%s, mot_de_passe=%s
                WHERE id=%s
            """, (nom, prenom, sexe, date_naissance, lieu_residence,
                  telephone, email, mot_de_passe, id))
        else:
            cur.execute("""
                UPDATE membres
                SET nom=%s, prenom=%s, sexe=%s, date_naissance=%s,
                    lieu_residence=%s, telephone=%s, email=%s
                WHERE id=%s
            """, (nom, prenom, sexe, date_naissance, lieu_residence,
                  telephone, email, id))

        conn.commit()
        cur.close()
        conn.close()

        return redirect(url_for('liste_membres'))

    cur.execute("SELECT * FROM membres WHERE id = %s", (id,))
    membre = cur.fetchone()

    cur.close()
    conn.close()

    return render_template('modifier_membre.html', membre=membre)

# ─── Route 11 : Supprimer un membre ──────────────────────────────────────────
@app.route('/membres/supprimer/<int:id>', methods=['POST'])
@gestionnaire_required
def supprimer_membre(id):
    conn = get_connection()
    cur  = conn.cursor()

    cur.execute("DELETE FROM membres WHERE id = %s", (id,))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for('liste_membres'))

# ─── Route 12 : Export PDF membres ───────────────────────────────────────────
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from flask import Response
import io

@app.route('/membres/pdf')
@gestionnaire_required
def export_membres_pdf():
    conn = get_connection()
    cur  = conn.cursor()

    cur.execute("""
        SELECT 
            nom, prenom, sexe,
            EXTRACT(YEAR FROM AGE(date_naissance)) AS age,
            lieu_residence, telephone, date_adhesion
        FROM membres
        ORDER BY nom
    """)
    membres = cur.fetchall()
    cur.close()
    conn.close()

    buffer = io.BytesIO()
    doc    = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    # Titre
    elements.append(Paragraph("Liste des membres", styles['Title']))
    elements.append(Spacer(1, 20))

    # Tableau
    data = [['Nom', 'Prénom', 'Sexe', 'Âge', 'Résidence', 'Téléphone', 'Adhésion']]
    for m in membres:
        data.append([m[0], m[1], m[2], f"{int(m[3])} ans", m[4], m[5], str(m[6])])

    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2c3e50')),
        ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
        ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE',   (0,0), (-1,0), 11),
        ('ALIGN',      (0,0), (-1,-1), 'CENTER'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f4f6f9')]),
        ('GRID',       (0,0), (-1,-1), 0.5, colors.grey),
        ('FONTSIZE',   (0,1), (-1,-1), 9),
        ('PADDING',    (0,0), (-1,-1), 6),
    ]))

    elements.append(table)
    doc.build(elements)

    buffer.seek(0)
    return Response(buffer, mimetype='application/pdf',
        headers={'Content-Disposition': 'attachment;filename=membres.pdf'})


# ─── Route 13 : Export PDF caisse ────────────────────────────────────────────
@app.route('/caisse/pdf')
@gestionnaire_required
def export_caisse_pdf():
    conn = get_connection()
    cur  = conn.cursor()

    cur.execute("""
        SELECT 
            p.libelle,
            p.montant_attendu * COUNT(m.id)      AS total_attendu,
            SUM(pa.montant_paye)                 AS total_collecte,
            p.montant_attendu * COUNT(m.id) 
                - SUM(pa.montant_paye)           AS manque_a_gagner
        FROM paiements pa
        JOIN membres  m ON pa.membre_id  = m.id
        JOIN periodes p ON pa.periode_id = p.id
        GROUP BY p.id, p.libelle, p.montant_attendu
        ORDER BY p.date_debut
    """)
    stats = cur.fetchall()
    cur.close()
    conn.close()

    buffer = io.BytesIO()
    doc    = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    # Titre
    elements.append(Paragraph("Statistiques de la caisse", styles['Title']))
    elements.append(Spacer(1, 20))

    # Tableau
    data = [['Période', 'Total attendu (FCFA)', 'Total collecté (FCFA)', 'Manque à gagner (FCFA)']]
    for s in stats:
        data.append([s[0], f"{s[1]:,.0f}", f"{s[2]:,.0f}", f"{s[3]:,.0f}"])

    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2c3e50')),
        ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
        ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE',   (0,0), (-1,0), 11),
        ('ALIGN',      (0,0), (-1,-1), 'CENTER'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f4f6f9')]),
        ('GRID',       (0,0), (-1,-1), 0.5, colors.grey),
        ('FONTSIZE',   (0,1), (-1,-1), 10),
        ('PADDING',    (0,0), (-1,-1), 8),
    ]))

    elements.append(table)
    doc.build(elements)

    buffer.seek(0)
    return Response(buffer, mimetype='application/pdf',
        headers={'Content-Disposition': 'attachment;filename=caisse.pdf'})

# ─── Route 14 : Export PDF paiements ─────────────────────────────────────────
@app.route('/paiements/pdf')
@gestionnaire_required
def export_paiements_pdf():
    conn = get_connection()
    cur  = conn.cursor()

    cur.execute("""
        SELECT 
            m.nom, m.prenom, p.libelle,
            pa.montant_paye, pa.date_paiement, pa.statut
        FROM paiements pa
        JOIN membres  m ON pa.membre_id  = m.id
        JOIN periodes p ON pa.periode_id = p.id
        ORDER BY p.date_debut, m.nom
    """)
    paiements = cur.fetchall()
    cur.close()
    conn.close()

    buffer = io.BytesIO()
    doc    = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("Liste des paiements", styles['Title']))
    elements.append(Spacer(1, 20))

    data = [['Nom', 'Prénom', 'Période', 'Montant payé (FCFA)', 'Date', 'Statut']]
    for p in paiements:
        data.append([p[0], p[1], p[2], f"{p[3]:,.0f}", str(p[4]), p[5]])

    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2c3e50')),
        ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
        ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE',   (0,0), (-1,0), 11),
        ('ALIGN',      (0,0), (-1,-1), 'CENTER'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f4f6f9')]),
        ('GRID',       (0,0), (-1,-1), 0.5, colors.grey),
        ('FONTSIZE',   (0,1), (-1,-1), 9),
        ('PADDING',    (0,0), (-1,-1), 6),
    ]))

    elements.append(table)
    doc.build(elements)

    buffer.seek(0)
    return Response(buffer, mimetype='application/pdf',
        headers={'Content-Disposition': 'attachment;filename=paiements.pdf'})


# ─── Route 15 : Export PDF pénalités ─────────────────────────────────────────
@app.route('/penalites/pdf')
@gestionnaire_required
def export_penalites_pdf():
    conn = get_connection()
    cur  = conn.cursor()

    cur.execute("""
        SELECT 
            m.nom, m.prenom, p.libelle,
            pe.montant_penalite, pe.motif,
            pe.date_application, pe.statut
        FROM penalites pe
        JOIN membres  m ON pe.membre_id  = m.id
        JOIN periodes p ON pe.periode_id = p.id
        ORDER BY pe.date_application DESC
    """)
    penalites = cur.fetchall()
    cur.close()
    conn.close()

    buffer = io.BytesIO()
    doc    = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("Liste des pénalités", styles['Title']))
    elements.append(Spacer(1, 20))

    data = [['Nom', 'Prénom', 'Période', 'Montant (FCFA)', 'Motif', 'Date', 'Statut']]
    for pe in penalites:
        data.append([pe[0], pe[1], pe[2], f"{pe[3]:,.0f}", pe[4], str(pe[5]), pe[6]])

    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2c3e50')),
        ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
        ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE',   (0,0), (-1,0), 11),
        ('ALIGN',      (0,0), (-1,-1), 'CENTER'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f4f6f9')]),
        ('GRID',       (0,0), (-1,-1), 0.5, colors.grey),
        ('FONTSIZE',   (0,1), (-1,-1), 9),
        ('PADDING',    (0,0), (-1,-1), 6),
    ]))

    elements.append(table)
    doc.build(elements)

    buffer.seek(0)
    return Response(buffer, mimetype='application/pdf',
        headers={'Content-Disposition': 'attachment;filename=penalites.pdf'})


# ─── Route : Espace membre ────────────────────────────────────────────────────
@app.route('/espace-membre')
def espace_membre():
    if 'logged_in' not in session or session['role'] != 'membre':
        return redirect(url_for('login'))

    membre_id = session['membre_id']
    conn = get_connection()
    cur  = conn.cursor()

    # Infos du membre
    cur.execute("""
        SELECT nom, prenom, sexe,
            EXTRACT(YEAR FROM AGE(date_naissance)) AS age,
            lieu_residence, telephone, date_adhesion
        FROM membres WHERE id = %s
    """, (membre_id,))
    membre = cur.fetchone()

    # Ses paiements
    cur.execute("""
        SELECT p.libelle, pa.montant_paye, pa.date_paiement, pa.statut
        FROM paiements pa
        JOIN periodes p ON pa.periode_id = p.id
        WHERE pa.membre_id = %s
        ORDER BY p.date_debut DESC
    """, (membre_id,))
    paiements = cur.fetchall()

    # Ses pénalités
    cur.execute("""
        SELECT p.libelle, pe.montant_penalite, pe.motif, pe.date_application, pe.statut
        FROM penalites pe
        JOIN periodes p ON pe.periode_id = p.id
        WHERE pe.membre_id = %s
        ORDER BY pe.date_application DESC
    """, (membre_id,))
    penalites = cur.fetchall()

    # Ses notifications
    cur.execute("""
        SELECT titre, message, date_envoi, lu
        FROM notifications
        WHERE membre_id = %s OR type = 'general'
        ORDER BY date_envoi DESC
    """, (membre_id,))
    notifications = cur.fetchall()

    # Marquer les notifications comme lues
    cur.execute("""
        UPDATE notifications 
        SET lu = TRUE 
        WHERE (membre_id = %s OR type = 'general') AND lu = FALSE
    """, (membre_id,))

    conn.commit()
    cur.close()
    conn.close()

    return render_template('espace_membre.html',
        membre        = membre,
        paiements     = paiements,
        penalites     = penalites,
        notifications = notifications
    )


# ─── Route : Envoyer une notification ────────────────────────────────────────
@app.route('/notifications/envoyer', methods=['GET', 'POST'])
@gestionnaire_required
def envoyer_notification():
    conn = get_connection()
    cur  = conn.cursor()

    if request.method == 'POST':
        titre     = request.form['titre']
        message   = request.form['message']
        type_notif = request.form['type_notif']
        membre_id = request.form.get('membre_id') or None

        cur.execute("""
            INSERT INTO notifications (titre, message, type, membre_id)
            VALUES (%s, %s, %s, %s)
        """, (titre, message, type_notif, membre_id))

        conn.commit()
        cur.close()
        conn.close()

        return redirect(url_for('liste_notifications'))

    cur.execute("SELECT id, nom, prenom FROM membres ORDER BY nom")
    membres = cur.fetchall()

    cur.close()
    conn.close()

    return render_template('envoyer_notification.html', membres=membres)


# ─── Route : Liste des notifications (gestionnaire) ───────────────────────────
@app.route('/notifications')
@gestionnaire_required
def liste_notifications():
    conn = get_connection()
    cur  = conn.cursor()

    cur.execute("""
        SELECT 
            n.titre, n.message, n.type,
            m.nom, m.prenom,
            n.date_envoi
        FROM notifications n
        LEFT JOIN membres m ON n.membre_id = m.id
        ORDER BY n.date_envoi DESC
    """)
    notifications = cur.fetchall()

    cur.close()
    conn.close()

    return render_template('notifications.html', notifications=notifications)





if __name__ == '__main__':
    app.run(debug=True)

