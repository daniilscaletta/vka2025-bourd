from collections import defaultdict

from flask_restx import Namespace, Resource
from flask import request
from sqlalchemy import select

from CTFd.cache import cache, make_cache_key
from CTFd.models import Awards, Solves, Users, db
from CTFd.utils import get_config
from CTFd.utils.dates import isoformat, unix_time_to_utc
from CTFd.utils.decorators.visibility import (
    check_account_visibility,
    check_score_visibility,
)
from CTFd.utils.modes import TEAMS_MODE, generate_account_url, get_mode_as_word
from CTFd.utils.scores import get_standings, get_user_standings

scoreboard_namespace = Namespace(
    "scoreboard", description="Endpoint to retrieve scores"
)


@scoreboard_namespace.route("")
class ScoreboardList(Resource):
    @check_account_visibility
    @check_score_visibility
    @cache.cached(timeout=60, key_prefix=make_cache_key)
    def get(self):
        top50 = request.cookies.get('top50') != "disabled"
        standings = get_standings()
        response = []
        mode = get_config("user_mode")
        account_type = get_mode_as_word()

        if mode == TEAMS_MODE:
            r = db.session.execute(
                select(
                    [
                        Users.id,
                        Users.name,
                        Users.oauth_id,
                        Users.team_id,
                        Users.hidden,
                        Users.banned,
                    ]
                ).where(Users.team_id.isnot(None))
            )
            users = r.fetchall()
            membership = defaultdict(dict)
            for u in users:
                if u.hidden is False and u.banned is False:
                    membership[u.team_id][u.id] = {
                        "id": u.id,
                        "oauth_id": u.oauth_id,
                        "name": u.name,
                        "score": 0,
                    }

            # Get user_standings as a dict so that we can more quickly get member scores
            user_standings = get_user_standings()
            for u in user_standings:
                membership[u.team_id][u.user_id]["score"] = int(u.score)

        for i, x in enumerate(standings):
            entry = {
                "pos": i + 1,
                "account_id": x.account_id,
                "account_url": generate_account_url(account_id=x.account_id),
                "account_type": account_type,
                "oauth_id": x.oauth_id,
                "name": x.name,
                "affiliation": x.affiliation,
                "score": int(x.score),
            }

            if mode == TEAMS_MODE:
                entry["members"] = list(membership[x.account_id].values())

            response.append(entry)
        return {"success": True, "data": response}


@scoreboard_namespace.route("/top/<count>")
@scoreboard_namespace.param("count", "How many top teams to return")
class ScoreboardDetail(Resource):
    @check_account_visibility
    @check_score_visibility
    @cache.cached(timeout=60, key_prefix=make_cache_key)
    def get(self, count):
        response = {}

        standings = get_standings(count=count)

        team_ids = [team.account_id for team in standings]

        solves = Solves.query.filter(Solves.account_id.in_(team_ids))
        awards = Awards.query.filter(Awards.account_id.in_(team_ids))

        freeze = get_config("freeze")

        if freeze:
            solves = solves.filter(Solves.date < unix_time_to_utc(freeze))
            awards = awards.filter(Awards.date < unix_time_to_utc(freeze))

        solves = solves.all()
        awards = awards.all()

        # Build a mapping of accounts to their solves and awards
        solves_mapper = defaultdict(list)
        for solve in solves:
            solves_mapper[solve.account_id].append(
                {
                    "challenge_id": solve.challenge_id,
                    "account_id": solve.account_id,
                    "team_id": solve.team_id,
                    "user_id": solve.user_id,
                    "value": solve.challenge.value,
                    "date": isoformat(solve.date),
                }
            )

        for award in awards:
            solves_mapper[award.account_id].append(
                {
                    "challenge_id": None,
                    "account_id": award.account_id,
                    "team_id": award.team_id,
                    "user_id": award.user_id,
                    "value": award.value,
                    "date": isoformat(award.date),
                }
            )

        # Sort all solves by date
        for team_id in solves_mapper:
            solves_mapper[team_id] = sorted(
                solves_mapper[team_id], key=lambda k: k["date"]
            )

        for i, _team in enumerate(team_ids):
            response[i + 1] = {
                "id": standings[i].account_id,
                "name": standings[i].name,
                "solves": solves_mapper.get(standings[i].account_id, []),
            }
        return {"success": True, "data": response}
