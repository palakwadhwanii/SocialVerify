import { Router } from "express";
import { getMonitoringOverviewHandler } from "../controllers/monitoringController";

const monitoringRouter = Router();

monitoringRouter.get("/", getMonitoringOverviewHandler);

export default monitoringRouter;

