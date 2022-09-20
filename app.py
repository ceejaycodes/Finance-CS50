import os
import time
import datetime
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, jsonify
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
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

# create the index function with log in required.


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    current_sessionid = session["user_id"]
    name = db.execute("SELECT username FROM users WHERE id = ?", current_sessionid)[0]["username"]
    balance = db.execute(
        "SELECT sum(stockamount) as stockamount, stocks, name, price, sum(buy_total) as buy_total  FROM dashboard WHERE userid = ? GROUP BY stocks HAVING sum(stockamount) > 0", current_sessionid)
    cash = db.execute("SELECT cash FROM users WHERE id = ?", current_sessionid)[0]["cash"]
    total_der = db.execute("SELECT sum(buy_total) as total FROM dashboard WHERE userid = ?", current_sessionid)[0]["total"]
    if total_der == None:
        total = 0
    else:
        total = total_der
    return render_template("index.html", balance=balance, cash=cash, total=total + cash, usd=usd, name=name)


# creating the buy route
@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "POST":
        # Declare variables
        current_sessionid = session["user_id"]
        stock_details = lookup(request.form.get("symbol"))
        available_balance = db.execute("SELECT cash FROM users WHERE id = ? ", current_sessionid)

        time = datetime.datetime.now()

        if not request.form.get("symbol"):
            return apology("please input a valid stock symbol", 400)
        elif not request.form.get("shares"):
            return apology("please input a valid number", 400)

        digs = request.form.get("shares")
        numberof_shares = int(digs)
        if numberof_shares <= 0:
            return apology("please input a valid amount of stocks", 400)
        elif not numberof_shares:
            return apology("please input a valid number", 400)
        elif stock_details == None:
            return apology("please select a valid symbol", 400)

        price = stock_details["price"]
        buytotal = price * numberof_shares
        if buytotal > available_balance[0]["cash"]:
            return apology("Insufficient Funds")
        try:
            name = stock_details["name"]
            available_cash = available_balance[0]["cash"] - buytotal
            transaction_type = 'Buy'
            db.execute("INSERT INTO dashboard (userid,stocks,stockamount,transaction_time,buy_total,price,name,transaction_type) VALUES(?,?,?,?,?,?,?,?)",
                       current_sessionid, request.form.get("symbol").upper(), numberof_shares, time, buytotal, price, name, transaction_type)
            db.execute("UPDATE users SET cash = ? WHERE id =?", available_cash, current_sessionid)
            flash("New Stocks Bought!")
            return redirect("/")
        except:
            return apology("invalid input", 400)

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    userid = session["user_id"]
    history = db.execute(
        "SELECT stocks, stockamount, price, transaction_time, transaction_type FROM dashboard WHERE userid = ?", userid)
    return render_template("history.html", history=history)


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
    """Get stock quote."""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        quote_l = lookup(symbol)
        if not symbol:
            return apology("Please input a stock Symbol")
        elif quote_l == None:
            return apology("Could Not Find Stock With That Symbol", 400)

        return render_template("quote1.html", quote_l=quote_l, symbol=symbol)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    session.clear()  # clear current session.

    if request.method == "POST":

        username = request.form.get("username")
        password = generate_password_hash(request.form.get("password"))

        # Ensure username was submitted
        if not username:
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # confirm password submitted
        elif not request.form.get("confirmation"):
            return apology("please confirm password", 400)

        # check if password and confirm password match
        elif not request.form.get("password") == request.form.get("confirmation"):
            return apology("password do not match")

        # check if username already exists, if not,add username and password to database
        try:
            db.execute("INSERT INTO users (username,hash) VALUES (?,?)", username, password)
        except:
            return apology("Username Exists Already")
        else:
            users = db.execute("SELECT * FROM users WHERE username = ?", username)
            session["user_id"] = users[0]["id"]
            return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    userid = session['user_id']
    symbol = request.form.get("symbol")
    sellamount = request.form.get("shares")
    stocks = db.execute("SELECT sum(stockamount) as stockamount, stocks FROM dashboard WHERE userid = ? GROUP BY stocks", userid)
    available_balance = db.execute("SELECT cash FROM users WHERE id = ? ", userid)
    stockamount = db.execute(
        "SELECT sum(stockamount) as stockamount FROM dashboard WHERE stocks = ? AND userid = ?", symbol, userid)
    if request.method == 'POST':

        if not symbol:
            return apology("Please Select A Stock To Sell", 400)

        elif not sellamount:
            return apology("Please Select A Stock To Sell", 400)

        elif int(sellamount) <= 0:
            return apology("Input A Valid Number Of Shares",400)

        elif int(sellamount) > stockamount[0]["stockamount"]:
            return apology("Not Enough Stocks!", 400)

        try:
            transaction_type = 'Sell'
            stock_details = lookup(request.form.get("symbol"))
            price = stock_details["price"]
            name = stock_details["name"]
            selltotal = price * int(sellamount)
            available_cash = available_balance[0]["cash"] + selltotal
            time = datetime.datetime.now()
            db.execute("INSERT INTO dashboard (userid,stocks,stockamount,transaction_time,buy_total,price,name,transaction_type) VALUES(?,?,?,?,?,?,?,?)",
                       userid, symbol, -int(sellamount), time, -selltotal, price, name, transaction_type)
            db.execute("UPDATE users SET cash = ? WHERE id =?", available_cash, userid)
            flash("Stocks Sold!")
            return redirect("/")
        except:
            return apology("invalid input",400)
    else:
        return render_template("sell.html", stocks=[stock["stocks"] for stock in stocks])


@app.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():
    if request.method == 'POST':
        userid = session["user_id"]
        amount = request.form.get("amount")
        cash = db.execute("SELECT cash FROM users WHERE id = ?", userid)
        if not amount:
            return apology("Ooops! You Didn't Add Any Cash", 403)
        elif int(amount) < 10:
            return apology("Minimum deposit is $10", 403)
        elif int(amount) > 100000:
            return apology("Maximum deposit is $100,000", 403)

        added_cash = cash[0]["cash"] + int(amount)
        db.execute("UPDATE users SET cash = ? WHERE id =?", added_cash, userid)
        flash("Funds Added!")
        return redirect("/")

    else:
        return render_template("deposit.html")


@app.route("/withdraw", methods=["GET", "POST"])
@login_required
def withdraw():
    if request.method == 'POST':
        userid = session["user_id"]
        amount = request.form.get("amount")
        cash = db.execute("SELECT cash FROM users WHERE id = ?", userid)

        if not amount:
            return apology("Ooops! You Didn't Withdraw Any Cash", 403)

        elif int(amount) > cash[0]["cash"]:
            return apology("You Dont Have That Much Money!", 403)

        elif int(amount) > 100000:
            return apology("Maximum wihtdrawal is $100,000", 403)

        added_cash = cash[0]["cash"] - int(amount)
        db.execute("UPDATE users SET cash = ? WHERE id =?", added_cash, userid)
        flash("Funds Withdrawn, Check your Bank!")
        return redirect("/")

    else:
        return render_template("withdraw.html")