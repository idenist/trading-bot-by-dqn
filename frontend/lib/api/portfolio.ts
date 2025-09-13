import { api } from "./client";
import { PortfolioSnapshot, Position } from "./types";

export const getPortfolio = () =>
  api.get<PortfolioSnapshot>("/portfolio").then(r => r.data);

export const getPositions = () =>
  api.get<Position[]>("/positions").then(r => r.data);
