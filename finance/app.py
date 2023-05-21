import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, jsonify
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    name={}
    price={}
    total={}
    cash_1 = db.execute("SELECT cash FROM users WHERE id=?",session["user_id"])
    cash = cash_1[0]["cash"]
    g_cash = cash
    rows = db.execute("SELECT symbol,quantity FROM holdings WHERE user_id=?",session["user_id"])
    for row in rows:
        name[row["symbol"]] = lookup(row["symbol"])["name"]
        price[row["symbol"]] = usd(lookup(row["symbol"])["price"])
        total[row["symbol"]] = usd(lookup(row["symbol"])["price"]*int(row["quantity"]))
        g_cash = g_cash + (lookup(row["symbol"])["price"]*int(row["quantity"]))
    return render_template("index.html",name=name,price=price,total=total,rows=rows,cash=usd(cash),g_cash=usd(g_cash))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "GET":
        return render_template("buy.html")
    else:
        funds = db.execute("SELECT cash FROM users WHERE id = ?",session["user_id"])
        if not request.form.get("symbol"):
            return apology("Please, enter the symbol of the company of which you want to buy the shares of.", 403)
        elif not request.form.get("shares"):
            return apology("Please, spesify the number of shares you want to buy.",403)
        elif int(request.form.get("shares")) < 0:
            return apology("Please, enter a valid value of shares.",403)
        elif lookup(request.form.get("symbol")) == None:
            return apology("Please, enter a valid symbol")
        elif funds[0]["cash"] < (lookup(request.form.get("symbol"))["price"]*int(request.form.get("shares"))):
            return apology("Sorry, you have inadequate funds.", 403)
        else:
            symbol = request.form.get("symbol")
            price = lookup(request.form.get("symbol"))["price"]
            quantity = int(request.form.get("shares"))
            total = lookup(request.form.get("symbol"))["price"]*int(request.form.get("shares"))
            now = datetime.now()
            dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
            transaction = db.execute("INSERT INTO transactions (user_id, date_time, symbol, price, quantity, total) VALUES (?, ?, ?, ?, ?, ?)", session["user_id"], dt_string, symbol, price, quantity, total)
            update = db.execute("UPDATE users SET cash=? WHERE id=?", (funds[0]["cash"]-total), session["user_id"])
            ros = db.execute("SELECT quantity FROM holdings WHERE user_id=? AND symbol=?", session["user_id"], symbol)
            if len(ros) < 1:
                update_holdings_1 = db.execute("INSERT INTO holdings (user_id, symbol, quantity) VALUES (?, ?, ?)", session["user_id"], symbol, quantity)
            else:
                update_holdings_2 = db.execute("UPDATE holdings SET quantity=? WHERE user_id=? AND symbol=?", (int(ros[0]["quantity"])+quantity), session["user_id"], symbol)
            flash("Sucssesfully bought!")
            return redirect("/")



@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    transactions = db.execute("SELECT * FROM transactions WHERE user_id=? ORDER BY id DESC",session["user_id"])
    return render_template("history.html", transactions=transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    if request.method == "GET":
        return render_template("quote.html")
    else:
        symbol = request.form.get("symbol")
        if lookup(symbol) == None:
            apology("Symbol invalid. Try Again!")
        else:
            quote = lookup(symbol)
            message = "A share of " + quote["name"] + "(" + quote["symbol"] + ")" + "will cost you " + usd(quote["price"]) + "."
            return render_template("quoted.html", message=message)



@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "GET":
        return render_template("register.html")
    else:
        red = db.execute("SELECT * FROM users WHERE username=:username", username=request.form.get("username"))
        if not request.form.get("username"):
            return apology("must provide username", 403)
        elif not request.form.get("password"):
            return apology("must provide password", 403)
        elif not request.form.get("password_a"):
            return apology("must Re-Enter Password", 403)
        elif request.form.get("password") != request.form.get("password_a"):
            return apology("must re-enter same password. Try again!", 403)
        elif len(red) > 0:
            return apology("Sorry! Username taken. Try Again", 403)
        else:
            hash_password = generate_password_hash(request.form.get("password"))
            row = db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", request.form.get("username"), hash_password)
            user = db.execute("SELECT * FROM users WHERE username=?", request.form.get("username"))
            session["user_id"] = user[0]["id"]
            flash("Registered!")
            return redirect("/")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "GET":
        symbols = db.execute("SELECT symbol,quantity FROM holdings WHERE user_id=?",session["user_id"])
        return render_template("sell.html", symbols=symbols)
    else:
        q = db.execute("SELECT quantity FROM holdings WHERE user_id=? AND symbol=?", session["user_id"], request.form.get("symbol"))
        quantity = q[0]["quantity"]
        c = db.execute("SELECT cash FROM users WHERE id=?",session["user_id"])
        cash = c[0]["cash"]
        if request.form.get("symbol") == None:
            return apology("Please, select a symbol.", 403)
        elif int(request.form.get("shares")) > quantity:
            return apology("You don't have enough shares.", 403)
        elif int(request.form.get("shares")) < 1:
            return apology("Invalid Input.", 403)
        else:
            now = datetime.now()
            dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
            symbol = request.form.get("symbol")
            price = lookup(symbol)["price"]
            total = price*int(request.form.get("shares"))
            transaction = db.execute("INSERT INTO transactions (user_id, date_time, symbol, price, quantity, total) VALUES (?, ?, ?, ?, ?, ?)", session["user_id"], dt_string, symbol, price, -int(request.form.get("shares")), total)
            update_holdings = db.execute("UPDATE holdings SET quantity=? WHERE user_id=? AND symbol=?", quantity-int(request.form.get("shares")), session["user_id"], symbol)
            update_users = db.execute("UPDATE users SET cash=? WHERE id=?", cash+total, session["user_id"])
            flash("Succesfully sold!")
            return redirect("/")


@app.route("/addcash", methods=["GET", "POST"])
@login_required
def addcash():
    if request.method == "GET":
        return render_template("addcash.html")
    else:
        if not request.form.get("amount"):
            return apology("Invalid Input", 403)
        else:
            c = db.execute("SELECT cash FROM users WHERE id=?", session["user_id"])
            cash = float(c[0]["cash"]) + float(request.form.get("amount"))
            update = db.execute("UPDATE users SET cash=? WHERE id=?", cash, session["user_id"])
            flash("Sucssesfully added cash!")
            return redirect("/")