#!/usr/bin/env python3
#
# Copyright Lightstep Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import base64
import json
import os
import random

import backoff
import requests
from flask import Flask, abort
from flask_sqlalchemy import SQLAlchemy
from opentelemetry import trace
from opentelemetry.exporter.jaeger import JaegerSpanExporter
from opentelemetry.sdk.trace.export import BatchExportSpanProcessor
from sqlalchemy import Column, ForeignKey, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship


app = Flask(__name__)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "MYSQL_URI", "mysql+mysqldb://mysql:mysql@localhost:3306/wfh"
)
db = SQLAlchemy(app)


class WFHAdvice(db.Model):
    __tablename__ = "wfh_advice"
    # Here we define columns for the table restaurant
    # Notice that each column is also a normal Python instance attribute.
    id = Column(Integer, primary_key=True)
    advice = Column(String(512), nullable=False)


trace.get_tracer_provider().add_span_processor(
    BatchExportSpanProcessor(
        JaegerSpanExporter(
            "flask-server",
            agent_host_name=os.getenv("OTEL_EXPORTER_JAEGER_AGENT_HOST", "localhost"),
        ),
    )
)


@app.route("/populate")
def populate():
    advice = []
    try:
        advice = WFHAdvice.query.all()
    except Exception:
        # ignore any errors here
        pass
    if len(advice) <= 0:
        db.create_all()
        advice_strings = {
            "Stock up on toilet paper",
            "Eat chips with chopsticks",
            "Get dressed before work",
            "Go for walks",
            "Get dressed before work",
            "Be aware of when your camera is on",
            "Maintain Regular Hours. Set a schedule, and stick to it",
            "Create a Morning Routine",
            "Place action figures or stuffies around your office to give you someone to talk to",
            "Set Ground Rules With the People in Your Space",
            "Schedule Breaks",
            "Take Breaks in Their Entirety",
            "Leave Home",
            "Focus on your most important work",
            "Listen to coffee shop soundtracks",
        }
        for advice in advice_strings:
            db.session.add(WFHAdvice(advice=advice))
        db.session.commit()
        return "success"
    return "already populated!"


@backoff.on_exception(
    backoff.expo, (requests.exceptions.Timeout, requests.exceptions.ConnectionError)
)
def get_count(advice):
    destination = os.getenv("DESTINATION", "http://localhost:8080")
    encoded = base64.b64encode(advice.encode("utf-8"))
    url = f"{destination}/frequency?tip={encoded}"
    res = requests.get(url)
    count = -1
    if res.status_code == 200:
        count = res.json().get("posts", -1)
    return count


@app.route("/help")
def help_from_the_internet():
    advices = WFHAdvice.query.all()
    if len(advices) <= 0:
        abort(404)
    advice = advices[random.randint(0, len(advices) - 1)].advice
    count = get_count(advice)
    output = {
        "tip": advice,
        "posts": count,
    }

    return json.dumps(output)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
