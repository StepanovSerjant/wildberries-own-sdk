import abc
from typing import Any, Coroutine, Union
from urllib import parse

import httpx
from camel_converter import dict_to_snake
from deepmerge import always_merger

from wildberriesownsdk.api.services import RequestService
from wildberriesownsdk.common import config
from wildberriesownsdk.common.exceptions import GettingDataFromAPIException
from wildberriesownsdk.common.utils import log_response


class WBAPIAction(RequestService):
    name = "default"
    help_text = "text about service"

    path = ""
    method = ""
    paginated = False

    data_field = ""

    def __init__(self, api_connector, page: int = 1):
        self.api_key = api_connector.api_key
        self.api_scopes = api_connector.scopes
        self.page = page  # 0 value - disable pagination

    def __str__(self) -> str:
        return (
            f"WB Сервис {self.name}\n{self.help_text}"
            if self.help_text
            else f"WB Сервис {self.name}"
        )

    @abc.abstractmethod
    def do(self) -> Any:
        if self.paginated:
            response_data = self.get_merged_response_data()
        else:
            response = self.perform_request()
            response_data = self.get_response_data(response)

        snaked_response_data = dict_to_snake(response_data)
        return (
            snaked_response_data[self.data_field]
            if self.data_field
            else snaked_response_data
        )

    @abc.abstractmethod
    async def async_do(self) -> Any:
        if self.paginated:
            response_data = self.get_merged_response_data()
        else:
            response = await self.async_perform_request()
            response_data = self.get_response_data(response)

        snaked_response_data = dict_to_snake(response_data)
        return (
            snaked_response_data[self.data_field]
            if self.data_field
            else snaked_response_data
        )

    def get_merged_response_data(self):
        merged_response_data = {}

        start_page = self.page
        while start_page:
            response = self.perform_request()
            response_data = self.get_response_data(response)

            next_page = response_data.pop("next", 0)
            merged_response_data = always_merger.merge(
                merged_response_data.copy(), response_data
            )

            if next_page and next_page > self.page:
                self.page = next_page
            else:
                break

        return merged_response_data

    def perform_request(self) -> httpx.Response:
        response = self.request(
            method=self.method,
            url=self.get_url(),
            json=self.get_body(),
            headers=self.get_auth_headers(),
        )
        log_response(response)
        return response

    async def async_perform_request(self) -> Coroutine:
        response = await self.async_request(
            method=self.method,
            url=self.get_url(),
            json=self.get_body(),
            headers=self.get_auth_headers(),
        )
        log_response(response)
        return response

    @property
    def pagination_query_params(self) -> dict:
        if self.paginated:
            return {
                "limit": 100,
                "next": self.page,
            }
        return {}

    def get_auth_headers(self) -> dict:
        return {"Authorization": self.api_key, "accept": "application/json"}

    def get_body(self) -> dict:
        return {}

    def get_url(self) -> str:
        url = f"{config.BASE_API_URL}/{config.API_VERSION}/{self.path}"
        query_params = self.get_query_params()
        if query_params:
            url_query = parse.urlencode(query_params)
            return f"{url}?{url_query}"

        return url

    def get_query_params(self) -> dict:
        return self.pagination_query_params

    def get_response_data(self, response: Union[httpx.Response, Coroutine]):
        response_status_code = response.status_code
        if 200 <= response_status_code < 400:
            return {} if response_status_code == 204 else response.json()
        else:
            raise GettingDataFromAPIException(
                f"Сервис {self.name} не смог получить данные.\n Статус код ответа сервера {response_status_code}"
            )
