from flask import Blueprint, render_template

all_rules = Blueprint("all_rules", __name__)

@all_rules.route("/all_rules")
def listing():
    return render_template("all_rules.html")
