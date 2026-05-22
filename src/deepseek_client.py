import asyncio
import json
import logging
import time
from typing import Optional

import aiohttp
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

logger = logging.getLogger(__name__)


class DeepSeekClientError(Exception):
    """Base exception for DeepSeek client errors."""


class DeepSeekRateLimitError(DeepSeekClientError):
    """Raised when rate limit is hit."""


class DeepSeekServerError(DeepSeekClientError):
    """Raised on server errors (5xx)."""


class DeepSeekClient:
    """Async client for DeepSeek-Flash API with retry logic."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com/v1",
        model: str = "deepseek-v4-flash",
        max_retries: int = 3,
        timeout: int = 120,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.max_retries = max_retries
        self.timeout = timeout

        # Setup logging
        os.makedirs("logs", exist_ok=True)
        self.api_logger = logging.getLogger("api_calls")
        self.api_logger.setLevel(logging.INFO)
        fh = logging.FileHandler("logs/api_calls.log", encoding="utf-8")
        fh.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
        )
        self.api_logger.addHandler(fh)

    def _log_api_call(self, prompt_tokens: int, completion_tokens: int, model: str):
        """Log API call details."""
        self.api_logger.info(
            f"model={model} | prompt_tokens={prompt_tokens} | "
            f"completion_tokens={completion_tokens} | total_tokens={prompt_tokens + completion_tokens}"
        )

    async def _make_request(
        self, session: aiohttp.ClientSession, payload: dict
    ) -> dict:
        """Make a single API request."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with session.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=self.timeout),
        ) as response:
            if response.status == 429:
                raise DeepSeekRateLimitError("Rate limit exceeded")
            if response.status >= 500:
                text = await response.text()
                raise DeepSeekServerError(f"Server error {response.status}: {text}")
            if response.status != 200:
                text = await response.text()
                raise DeepSeekClientError(
                    f"API error {response.status}: {text}"
                )

            return await response.json()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        retry=retry_if_exception_type(
            (DeepSeekRateLimitError, DeepSeekServerError, aiohttp.ClientError)
        ),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def call(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4000,
    ) -> str:
        """
        Call DeepSeek-Flash API with the given prompt.

        Args:
            prompt: User prompt text
            system_prompt: Optional system prompt
            temperature: Model temperature (0.0 - 2.0)
            max_tokens: Maximum tokens in response

        Returns:
            Response text from the model
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        logger.debug(f"Sending request to DeepSeek API. Prompt length: {len(prompt)}")

        async with aiohttp.ClientSession() as session:
            result = await self._make_request(session, payload)

        # Extract response text
        try:
            response_text = result["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise DeepSeekClientError(f"Unexpected API response format: {result}") from e

        # Log token usage
        usage = result.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        self._log_api_call(prompt_tokens, completion_tokens, self.model)

        logger.debug(
            f"Received response. Length: {len(response_text)}, "
            f"Tokens: {prompt_tokens + completion_tokens}"
        )

        return response_text

    async def call_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> dict:
        """
        Call DeepSeek API and parse response as JSON.

        Returns:
            Parsed JSON response as dict
        """
        response = await self.call(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # Try to extract JSON from response
        response = response.strip()
        # Remove markdown code blocks if present
        if response.startswith("```"):
            lines = response.split("\n")
            # Find first and last ```
            start = 0
            end = len(lines)
            for i, line in enumerate(lines):
                if line.strip().startswith("```"):
                    if start == 0:
                        start = i + 1
                    else:
                        end = i
                        break
            response = "\n".join(lines[start:end])

        try:
            return json.loads(response.strip())
        except json.JSONDecodeError as e:
            raise DeepSeekClientError(
                f"Failed to parse JSON response: {e}\nResponse: {response[:500]}"
            )
