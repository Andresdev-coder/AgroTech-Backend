import json
import os
from datetime import datetime
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.dependencies import require_roles

router = APIRouter(
    prefix="/api/clima",
    tags=["Clima"],
    dependencies=[Depends(require_roles("admin", "bodeguero", "ventas"))],
)

DEFAULT_CITY = os.getenv("OPENWEATHER_DEFAULT_CITY", "Yopal")
DEFAULT_COUNTRY = os.getenv("OPENWEATHER_DEFAULT_COUNTRY", "CO")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
OPENWEATHER_LANG = os.getenv("OPENWEATHER_LANG", "es")


def _fetch_json(url: str) -> dict:
    request = Request(url, headers={"User-Agent": "AgroTech/1.0"})
    with urlopen(request, timeout=15) as response:
      return json.loads(response.read().decode("utf-8"))


def _build_geocoding_url(city: str, country: str) -> str:
    params = urlencode(
        {
            "q": f"{city},{country}",
            "limit": 1,
            "appid": OPENWEATHER_API_KEY,
        }
    )
    return f"https://api.openweathermap.org/geo/1.0/direct?{params}"


def _build_weather_url(lat: float, lon: float) -> str:
    params = urlencode(
        {
            "lat": lat,
            "lon": lon,
            "appid": OPENWEATHER_API_KEY,
            "units": "metric",
            "lang": OPENWEATHER_LANG,
        }
    )
    return f"https://api.openweathermap.org/data/2.5/weather?{params}"


@router.get("")
def obtener_clima(
    city: str = Query(DEFAULT_CITY, min_length=2),
    country: str = Query(DEFAULT_COUNTRY, min_length=2, max_length=2),
):
    if not OPENWEATHER_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="Falta configurar OPENWEATHER_API_KEY en el entorno del backend.",
        )

    try:
        geocoding_url = _build_geocoding_url(city.strip(), country.strip())
        locations = _fetch_json(geocoding_url)

        if not locations:
            raise HTTPException(
                status_code=404,
                detail=f"No se encontro la ubicacion '{city}, {country}'.",
            )

        location = locations[0]
        weather_data = _fetch_json(
            _build_weather_url(float(location["lat"]), float(location["lon"]))
        )

        main = weather_data.get("main", {})
        wind = weather_data.get("wind", {})
        clouds = weather_data.get("clouds", {})
        weather = (weather_data.get("weather") or [{}])[0]

        temp = float(main.get("temp") or 0)
        humidity = int(main.get("humidity") or 0)
        pressure = int(main.get("pressure") or 0)
        wind_speed = float(wind.get("speed") or 0)
        cloudiness = int(clouds.get("all") or 0)
        description = weather.get("description") or "Sin descripcion"
        icon = weather.get("icon") or "01d"
        feels_like = float(main.get("feels_like") or temp)
        temp_min = float(main.get("temp_min") or temp)
        temp_max = float(main.get("temp_max") or temp)

        if temp >= 32:
            recomendacion = "Maneja riego temprano y evita labores pesadas al mediodia."
        elif humidity >= 80:
            recomendacion = "Vigila hongos y humedad alta en cultivos sensibles."
        elif wind_speed >= 8:
            recomendacion = "Asegura estructuras livianas y revisa aplicaciones foliares."
        elif cloudiness >= 70:
            recomendacion = "Mantente atento a cambios bruscos y posible lluvia."
        else:
            recomendacion = "Condiciones favorables para labores de campo y aplicacion."

        return {
            "ubicacion": {
                "ciudad": location.get("name", city),
                "pais": location.get("country", country),
                "estado": location.get("state"),
                "lat": location.get("lat"),
                "lon": location.get("lon"),
            },
            "actual": {
                "temperatura": round(temp, 1),
                "sensacion": round(feels_like, 1),
                "descripcion": description,
                "icono": icon,
                "humedad": humidity,
                "viento": round(wind_speed, 1),
                "presion": pressure,
                "nubosidad": cloudiness,
                "temp_min": round(temp_min, 1),
                "temp_max": round(temp_max, 1),
                "actualizado_en": datetime.utcfromtimestamp(weather_data.get("dt", 0)).isoformat(),
            },
            "recomendacion": recomendacion,
        }
    except HTTPError as error:
        detail = error.read().decode("utf-8") if error.fp else str(error)
        raise HTTPException(status_code=502, detail=f"OpenWeather devolvio un error: {detail}")
    except URLError as error:
        raise HTTPException(status_code=502, detail=f"No se pudo conectar con OpenWeather: {error.reason}")
