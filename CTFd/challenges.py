from flask import Blueprint, redirect, render_template, request, url_for
from CTFd.models import Teams
from CTFd.constants.config import ChallengeVisibilityTypes, Configs
from CTFd.utils.config import is_teams_mode
from CTFd.utils.dates import ctf_ended, ctf_paused, ctf_started
from CTFd.utils.user import get_current_user, get_current_user_attrs, authed
from CTFd.utils.decorators import (
    during_ctf_time_only,
    require_complete_profile,
    require_verified_emails,
)
from CTFd.utils.decorators.visibility import check_challenge_visibility
from CTFd.utils.helpers import get_errors, get_infos
from CTFd.utils.user import authed, get_current_team
from CTFd.utils.decorators.modes import require_team_mode
from CTFd.utils.decorators.visibility import (
    check_account_visibility,
    check_score_visibility,
)


challenges = Blueprint("challenges", __name__)


from CTFd.models import Teams
from CTFd.utils.user import get_current_team

@challenges.route("/challenges", methods=["GET"])
@require_complete_profile
@during_ctf_time_only
@require_verified_emails
@check_challenge_visibility
@check_account_visibility
@check_score_visibility
@require_team_mode
def listing():
    team = get_current_team()
    
    if team is None or team.banned or team.hidden:
        return redirect(url_for("teams.private", next=request.full_path))
    
    score = team.score or 0  # на всякий случай

    if (
        Configs.challenge_visibility == ChallengeVisibilityTypes.PUBLIC
        and authed() is False
    ):
        pass
    else:
        if is_teams_mode() and team is None:
            return redirect(url_for("teams.private", next=request.full_path))

    infos = get_infos()
    errors = get_errors()

    if not ctf_started():
        errors.append(f"{Configs.ctf_name} has not started yet")

    if ctf_paused():
        infos.append(f"{Configs.ctf_name} is paused")

    if ctf_ended():
        infos.append(f"{Configs.ctf_name} has ended")

    return render_template("challenges.html", infos=infos, errors=errors, score=score)

