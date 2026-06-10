# Architecture

This project uses a pragmatic 2.5D virtual fitting architecture. SAM 3D Body is used to lock the body ratio and pose guide. The garment generation step produces front, side, and back visual outputs instead of a full cloth-simulation mesh.

## Repository Map

```mermaid
flowchart TD
  Repo[Capstone-BIG4 AI repo]
  Repo --> FE[frontend]
  Repo --> BE[backend/app]
  Repo --> AI[scripts]
  Repo --> Assets[assets]
  Repo --> Docs[docs]

  FE --> UI[Studio UI]
  FE --> Viewer[2.5D viewer]
  BE --> API[FastAPI endpoints]
  BE --> Jobs[Run and job state]
  AI --> SAM[SAM 3D Body stage]
  AI --> Guide[Guide rendering]
  AI --> VTON[VTON generation]
  AI --> Final[Mask-locked finalization]
  Assets --> Display[Selected viewer outputs]
  Docs --> Mermaid[Mermaid diagrams]
```

## Component Boundaries

```mermaid
flowchart LR
  subgraph Client
    Browser[Browser UI]
    UploadSlots[5 required upload slots]
    ViewerTabs[Front / Side / Back tabs]
  end

  subgraph Server
    FastAPI[FastAPI app]
    UploadService[Upload service]
    ResultService[Result service]
    Runner[Pipeline runner]
  end

  subgraph AI
    Preprocess[Preprocess]
    Body[SAM 3D Body]
    Guides[Guide maps]
    Generate[VTON candidates]
    Select[Final selection]
  end

  Browser --> FastAPI
  UploadSlots --> UploadService
  FastAPI --> Runner
  Runner --> Preprocess
  Preprocess --> Body
  Body --> Guides
  Guides --> Generate
  Generate --> Select
  Select --> ResultService
  ResultService --> ViewerTabs
```

## Data Flow

```mermaid
flowchart TD
  Person[User full-body photo]
  TopFront[Top front]
  TopBack[Top back]
  PantsFront[Pants front]
  PantsBack[Pants back]

  Person --> Crop[Person crop and orientation]
  Crop --> Mesh[SAM 3D Body mesh/body]
  Mesh --> Guides[Front/side/back guide maps]

  TopFront --> GarmentPrep[Garment preprocessing]
  TopBack --> GarmentPrep
  PantsFront --> GarmentPrep
  PantsBack --> GarmentPrep

  Guides --> BodyBase[SAM body mannequin base]
  BodyBase --> VTON[VTON candidate generation]
  GarmentPrep --> VTON
  VTON --> MaskLock[Garment mask lock]
  MaskLock --> Polish[Viewer framing and contrast]
  Polish --> Outputs[2D result + front/side/back viewer]
```

## State Model

```mermaid
stateDiagram-v2
  [*] --> Idle
  Idle --> Uploading: user selects files
  Uploading --> Ready: five slots available
  Ready --> Running: Run Fitting
  Running --> Completed: result contract valid
  Running --> Failed: pipeline or artifact error
  Completed --> Idle: Reset
  Failed --> Idle: Reset
```

## Viewer Contract

```mermaid
flowchart LR
  ResultAPI[GET /api/results]
  ResultAPI --> TwoD[tryon-2d.png]
  ResultAPI --> Front[front viewer image]
  ResultAPI --> Side[side viewer image]
  ResultAPI --> Back[back viewer image]
  Front --> Tabs[Viewer tabs]
  Side --> Tabs
  Back --> Tabs
```
