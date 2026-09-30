"""
Smart Road Pothole Detection & Management System — backend package.

Layout (mirrors a typical layered/MVC backend — controller/service/
repository/entity/dto — just in FastAPI + Python naming):

  app/
    core/        settings + auth/security   (like FarmVerse's `config/`)
    db/          DB engine/session setup
    models/      SQLAlchemy ORM entities     (like FarmVerse's `entity/`)
    schemas/     Pydantic request/response
                 models                      (like FarmVerse's `dto/`)
    repository/  raw DB access (CRUD)        (like FarmVerse's `repository/`)
    services/    business logic              (like FarmVerse's `service/`)
    routers/     HTTP endpoints              (like FarmVerse's `controller/`)
    utils/       small stateless helpers

Every feature (health, prediction, complaints, insights, drift) gets its
own router + service (+ repository/schema where relevant), instead of one
big main.py.
"""
