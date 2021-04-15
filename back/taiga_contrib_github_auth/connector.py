# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2021-present Kaleidos Ventures SL

import requests
import json

from collections import namedtuple
from urllib.parse import urljoin

from django.conf import settings
from django.utils.translation import ugettext_lazy as _

from taiga.base.connectors.exceptions import ConnectorBaseException


class GitHubApiError(ConnectorBaseException):
    pass


######################################################
## Data
######################################################

CLIENT_ID = getattr(settings, "GITHUB_API_CLIENT_ID", None)
CLIENT_SECRET = getattr(settings, "GITHUB_API_CLIENT_SECRET", None)

URL = getattr(settings, "GITHUB_URL", "https://github.com/")
API_URL = getattr(settings, "GITHUB_API_URL",  "https://api.github.com/")
API_RESOURCES_URLS = {
    "login": {
        "authorize": "login/oauth/authorize",
        "access-token": "login/oauth/access_token"
    },
    "user": {
        "profile": "user",
        "emails": "user/emails"
    }
}


HEADERS = {"Accept": "application/json",}

AuthInfo = namedtuple("AuthInfo", ["access_token"])
User = namedtuple("User", ["id", "username", "full_name", "bio"])
Email = namedtuple("Email", ["email", "is_primary"])


######################################################
## utils
######################################################

def _build_url(*args, **kwargs) -> str:
    """
    Return a valid url.
    """
    resource_url = API_RESOURCES_URLS
    for key in args:
        resource_url = resource_url[key]

    if kwargs:
        resource_url = resource_url.format(**kwargs)

    return urljoin(API_URL, resource_url)


def _get(url:str, headers:dict) -> dict:
    """
    Make a GET call.
    """
    response = requests.get(url, headers=headers)

    data = response.json()
    if response.status_code != 200:
        raise GitHubApiError({"status_code": response.status_code,
                                  "error": data.get("error", "")})
    return data


def _post(url:str, params:dict, headers:dict) -> dict:
    """
    Make a POST call.
    """
    response = requests.post(url, params=params, headers=headers)

    data = response.json()
    if response.status_code != 200 or "error" in data:
        raise GitHubApiError({"status_code": response.status_code,
                                  "error": data.get("error", "")})
    return data


######################################################
## Simple calls
######################################################

def login(access_code:str, client_id:str=CLIENT_ID, client_secret:str=CLIENT_SECRET,
          headers:dict=HEADERS):
    """
    Get access_token fron an user authorized code, the client id and the client secret key.
    (See https://developer.github.com/v3/oauth/#web-application-flow).
    """
    if not CLIENT_ID or not CLIENT_SECRET:
        raise GitHubApiError({"error_message": _("Login with github account is disabled. Contact "
                                                     "with the sysadmins. Maybe they're snoozing in a "
                                                     "secret hideout of the data center.")})

    url = urljoin(URL, "login/oauth/access_token")
    params={"code": access_code,
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "user:emails"}
    data = _post(url, params=params, headers=headers)
    return AuthInfo(access_token=data.get("access_token", None))


def get_user_profile(headers:dict=HEADERS):
    """
    Get authenticated user info.
    (See https://developer.github.com/v3/users/#get-the-authenticated-user).
    """
    url = _build_url("user", "profile")
    data = _get(url, headers=headers)
    return User(id=data.get("id", None),
                username=data.get("login", None),
                full_name=(data.get("name", None) or ""),
                bio=(data.get("bio", None) or ""))


def get_user_emails(headers:dict=HEADERS) -> list:
    """
    Get a list with all emails of the authenticated user.
    (See https://developer.github.com/v3/users/emails/#list-email-addresses-for-a-user).
    """
    url = _build_url("user", "emails")
    data = _get(url, headers=headers)
    return [Email(email=e.get("email", None), is_primary=e.get("primary", False))
                    for e in data]


######################################################
## Convined calls
######################################################

def me(access_code:str) -> tuple:
    """
    Connect to a github account and get all personal info (profile and the primary email).
    """
    auth_info = login(access_code)

    headers = HEADERS.copy()
    headers["Authorization"] = "token {}".format(auth_info.access_token)

    user = get_user_profile(headers=headers)
    emails = get_user_emails(headers=headers)

    primary_email = next(filter(lambda x: x.is_primary, emails))
    return primary_email.email, user

