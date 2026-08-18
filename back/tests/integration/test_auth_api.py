# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2021-present Kaleidos INC

import pytest
from unittest.mock import patch

from django.apps import apps
from django.core.urlresolvers import reverse

from .. import factories

from taiga_contrib_github_auth import connector as github_connector

pytestmark = pytest.mark.django_db


def test_response_200_in_registration_with_github_account(client, settings):
    settings.PUBLIC_REGISTER_ENABLED = False
    form = {"type": "github",
            "code": "xxxxxx"}

    auth_data_model = apps.get_model("users", "AuthData")

    with patch("taiga_contrib_github_auth.connector.me") as m_me:
        m_me.return_value = ("mmcfly@bttf.com", True,
                             github_connector.User(id=1955,
                                                   username="mmcfly",
                                                   full_name="martin seamus mcfly",
                                                   bio="time traveler"))

        response = client.post(reverse("auth-list"), form)
        assert response.status_code == 200
        assert response.data["username"] == "mmcfly"
        assert response.data["auth_token"] != "" and response.data["auth_token"] is not None
        assert response.data["email"] == "mmcfly@bttf.com"
        assert response.data["full_name"] == "martin seamus mcfly"
        assert response.data["bio"] == "time traveler"
        assert auth_data_model.objects.filter(user__username="mmcfly", key="github", value="1955").count() == 1


def test_response_200_in_registration_with_github_account_and_existed_user_by_email(client, settings):
    settings.PUBLIC_REGISTER_ENABLED = False
    form = {"type": "github",
            "code": "xxxxxx"}
    user = factories.UserFactory()
    user.email = "mmcfly@bttf.com"
    user.save()

    with patch("taiga_contrib_github_auth.connector.me") as m_me:
        m_me.return_value = ("mmcfly@bttf.com", True,
                             github_connector.User(id=1955,
                                                   username="mmcfly",
                                                   full_name="martin seamus mcfly",
                                                   bio="time traveler"))

        response = client.post(reverse("auth-list"), form)
        assert response.status_code == 200
        assert response.data["username"] == user.username
        assert response.data["auth_token"] != "" and response.data["auth_token"] is not None
        assert response.data["email"] == user.email
        assert response.data["full_name"] == user.full_name
        assert response.data["bio"] == user.bio
        assert user.auth_data.filter(key="github", value="1955").count() == 1


def test_response_401_in_registration_with_new_github_user_with_unverified_email(client, settings):
    settings.PUBLIC_REGISTER_ENABLED = False
    form = {"type": "github",
            "code": "xxxxxx"}
    user_model = apps.get_model("users", "User")
    auth_data_model = apps.get_model("users", "AuthData")
    user_count = user_model.objects.count()
    auth_data_count = auth_data_model.objects.count()

    with patch("taiga_contrib_github_auth.connector.me") as m_me:
        m_me.return_value = ("unverified@example.com", False,
                             github_connector.User(id=999,
                                                   username="unverified-user",
                                                   full_name="unverified user",
                                                   bio=""))

        response = client.post(reverse("auth-list"), form)

    assert response.status_code == 401
    assert response.data["detail"]["code"] == "sso_authentication_failed"
    assert "auth_token" not in response.data
    assert user_model.objects.count() == user_count
    assert auth_data_model.objects.count() == auth_data_count


def test_response_401_in_registration_with_new_github_user_without_email(client, settings):
    settings.PUBLIC_REGISTER_ENABLED = False
    form = {"type": "github",
            "code": "xxxxxx"}
    user_model = apps.get_model("users", "User")
    auth_data_model = apps.get_model("users", "AuthData")
    user_count = user_model.objects.count()
    auth_data_count = auth_data_model.objects.count()

    with patch("taiga_contrib_github_auth.connector.me") as m_me:
        m_me.return_value = (None, True,
                             github_connector.User(id=999,
                                                   username="missing-email",
                                                   full_name="missing email",
                                                   bio=""))

        response = client.post(reverse("auth-list"), form)

    assert response.status_code == 401
    assert response.data["detail"]["code"] == "sso_authentication_failed"
    assert "auth_token" not in response.data
    assert user_model.objects.count() == user_count
    assert auth_data_model.objects.count() == auth_data_count


def test_unverified_existing_email_has_no_side_effects(client, settings):
    settings.PUBLIC_REGISTER_ENABLED = False
    membership_model = apps.get_model("projects", "Membership")
    membership = factories.MembershipFactory(user=None)
    user = factories.UserFactory.create(email="victim@example.com")
    user_model = apps.get_model("users", "User")
    auth_data_model = apps.get_model("users", "AuthData")
    user_count = user_model.objects.count()
    auth_data_count = auth_data_model.objects.count()
    form = {"type": "github",
            "code": "xxxxxx",
            "token": membership.token,
            "invitation_token": membership.token}

    with patch("taiga_contrib_github_auth.connector.me") as m_me, \
            patch("taiga_contrib_github_auth.services.make_auth_response_data") as m_make_auth_response_data, \
            patch("taiga_contrib_github_auth.services.send_register_email") as m_send_register_email, \
            patch("taiga_contrib_github_auth.services.user_registered_signal.send") as m_user_registered, \
            patch("taiga_contrib_github_auth.services.get_membership_by_token") as m_get_membership_by_token, \
            patch("taiga.auth.api.accept_invitation_by_existing_user") as m_accept_invitation:
        m_me.return_value = ("victim@example.com", False,
                             github_connector.User(id=999,
                                                   username="unverified-user",
                                                   full_name="unverified user",
                                                   bio=""))

        response = client.post(reverse("auth-list"), form)

    assert response.status_code == 401
    assert response.data["detail"]["code"] == "sso_authentication_failed"
    assert "auth_token" not in response.data
    assert user_model.objects.count() == user_count
    assert auth_data_model.objects.count() == auth_data_count
    assert user.auth_data.filter(key="github", value="999").count() == 0
    assert membership_model.objects.get(pk=membership.pk).user_id is None
    m_make_auth_response_data.assert_not_called()
    m_send_register_email.assert_not_called()
    m_user_registered.assert_not_called()
    m_get_membership_by_token.assert_not_called()
    m_accept_invitation.assert_not_called()


def test_response_200_in_registration_with_github_account_and_existed_user_by_github_id(client, settings):
    settings.PUBLIC_REGISTER_ENABLED = False
    form = {"type": "github",
            "code": "xxxxxx"}
    user = factories.UserFactory.create()

    auth_data_model = apps.get_model("users", "AuthData")
    auth_data_model.objects.create(user=user, key="github", value="1955", extra={})

    with patch("taiga_contrib_github_auth.connector.me") as m_me:
        m_me.return_value = ("mmcfly@bttf.com", False,
                             github_connector.User(id=1955,
                                                   username="mmcfly",
                                                   full_name="martin seamus mcfly",
                                                   bio="time traveler"))

        response = client.post(reverse("auth-list"), form)
        assert response.status_code == 200
        assert response.data["username"] != "mmcfly"
        assert response.data["auth_token"] != "" and response.data["auth_token"] is not None
        assert response.data["email"] != "mmcfly@bttf.com"
        assert response.data["full_name"] != "martin seamus mcfly"
        assert response.data["bio"] != "time traveler"


def test_response_200_in_registration_with_github_account_and_change_github_username(client, settings):
    settings.PUBLIC_REGISTER_ENABLED = False
    form = {"type": "github",
            "code": "xxxxxx"}
    user = factories.UserFactory()
    user.username = "mmcfly"
    user.save()

    auth_data_model = apps.get_model("users", "AuthData")

    with patch("taiga_contrib_github_auth.connector.me") as m_me:
        m_me.return_value = ("mmcfly@bttf.com", True,
                             github_connector.User(id=1955,
                                                   username="mmcfly",
                                                   full_name="martin seamus mcfly",
                                                   bio="time traveler"))

        response = client.post(reverse("auth-list"), form)
        assert response.status_code == 200
        assert response.data["username"] == "mmcfly-1"
        assert response.data["auth_token"] != "" and response.data["auth_token"] is not None
        assert response.data["email"] == "mmcfly@bttf.com"
        assert response.data["full_name"] == "martin seamus mcfly"
        assert response.data["bio"] == "time traveler"
        assert auth_data_model.objects.filter(user__username="mmcfly-1", key="github", value="1955").count() == 1


def test_response_200_in_registration_with_github_account_in_a_project(client, settings):
    settings.PUBLIC_REGISTER_ENABLED = False
    membership_model = apps.get_model("projects", "Membership")
    membership = factories.MembershipFactory(user=None)
    form = {"type": "github",
            "code": "xxxxxx",
            "token": membership.token}

    with patch("taiga_contrib_github_auth.connector.me") as m_me:
        m_me.return_value = ("mmcfly@bttf.com", True,
                             github_connector.User(id=1955,
                                                   username="mmcfly",
                                                   full_name="martin seamus mcfly",
                                                   bio="time traveler"))

        response = client.post(reverse("auth-list"), form)
        assert response.status_code == 200
        assert membership_model.objects.get(token=form["token"]).user.username == "mmcfly"


def test_response_404_in_registration_with_github_in_a_project_with_invalid_token(client, settings):
    settings.PUBLIC_REGISTER_ENABLED = False
    form = {"type": "github",
            "code": "xxxxxx",
            "token": "123456"}

    with patch("taiga_contrib_github_auth.connector.me") as m_me:
        m_me.return_value = ("mmcfly@bttf.com", True,
                             github_connector.User(id=1955,
                                                   username="mmcfly",
                                                   full_name="martin seamus mcfly",
                                                   bio="time traveler"))

        response = client.post(reverse("auth-list"), form)
        assert response.status_code == 404
