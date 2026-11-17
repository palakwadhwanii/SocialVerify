import type { Request, Response } from "express";
import { db } from "../prisma/db";
import { ConversationVariant } from "../prisma/enums";
import { createResearchPdf } from "../services/reportService";
import { parseConversationId, parseUserId } from "../utils/ids";

function getInvestigationData(content: string | null) {
    const encoded = content?.match(/<!-- socialverify-investigation:v1:([A-Za-z0-9_-]+) -->/)?.[1];
    if (!encoded) return null;

    const parsed: unknown = JSON.parse(Buffer.from(encoded, "base64url").toString("utf8"));
    if (
        !parsed ||
        typeof parsed !== "object" ||
        !("window" in parsed) ||
        !("spread" in parsed) ||
        !("source_records" in parsed)
    ) {
        throw new Error("Stored investigation data is malformed.");
    }
    return parsed;
}

export async function getConversationHandler(req: Request, res: Response) {
    try {
        const userId = parseUserId(req.userId);
        if (!userId) return res.status(401).json({ success: false, message: "Unauthorized access." });
        const conversations = await db.orm.public.Conversation
            .where({ userId })
            .include("chats", (chats) => chats.count())
            .orderBy((conversation) => conversation.lastUpdated.desc())
            .all();

        return res.status(200).json({
            success: true,
            message: "Conversations fetched successfully",
            data: conversations.map(({ chats, ...conversation }) => ({
                ...conversation,
                _count: { chats },
            })),
        });
    } catch (error) {
        console.error("Error getting conversations:", error);
        return res.status(500).json({
            success: false,
            message: "An error occurred while getting the conversation.",
            error: error instanceof Error ? error.message : String(error),
        });
    }
}

export async function getConversationInvestigationHandler(req: Request, res: Response) {
    try {
        const userId = parseUserId(req.userId);
        const conversationId = parseConversationId(req.params.conversationId);
        if (!userId) return res.status(401).json({ success: false, message: "Unauthorized access." });
        if (!conversationId) {
            return res.status(400).json({ success: false, message: "Conversation ID is required." });
        }
        const conversation = await db.orm.public.Conversation
            .where({ id: conversationId, userId })
            .first();
        if (!conversation) {
            return res.status(404).json({ success: false, message: "Conversation not found." });
        }
        const messages = await db.orm.public.Chat
            .where({ conversationId })
            .orderBy((chat) => chat.createdAt.asc())
            .all();
        const report = [...messages].reverse().find((message) => message.sender === "bot");
        return res.status(200).json({
            success: true,
            message: "Investigation data fetched successfully.",
            data: getInvestigationData(report?.content ?? null),
        });
    } catch (error) {
        console.error("Error getting structured investigation data:", error);
        return res.status(500).json({
            success: false,
            message: "The structured investigation data could not be read.",
        });
    }
}

export async function postConversationHandler(req: Request, res: Response) {
    try {
        const userId = parseUserId(req.userId);
        if (!userId) return res.status(401).json({ success: false, message: "Unauthorized access." });
        const { title, variant } = req.body;
        if (!title || !Object.values(ConversationVariant).includes(variant)) {
            return res.status(400).json({
                success: false,
                message: "Conversation title and variant are required.",
            });
        }
        const conversation = await db.orm.public.Conversation.create({
            userId,
            title,
            variant,
        });
        return res.status(201).json({
            success: true,
            message: "Conversation created successfully",
            data: conversation,
        });
    } catch (error) {
        console.error("Error creating conversation:", error);
        return res.status(500).json({
            success: false,
            message: "An error occurred while creating the conversation.",
            error: error instanceof Error ? error.message : String(error),
        });
    }
}

export async function deleteConversationHandler(req: Request, res: Response) {
    try {
        const userId = parseUserId(req.userId);
        const conversationId = parseConversationId(req.params.conversationId);
        if (!userId) return res.status(401).json({ success: false, message: "Unauthorized access." });
        if (!conversationId) {
            return res.status(400).json({
                success: false,
                message: "Conversation ID is required.",
            });
        }
        const conversation = await db.orm.public.Conversation
            .where({ id: conversationId, userId })
            .first();
        if (!conversation) {
            return res.status(404).json({
                success: false,
                message: "Conversation not found",
            });
        }
        await db.orm.public.Conversation.where({ id: conversationId }).delete();
        return res.status(200).json({
            success: true,
            message: "Conversation deleted successfully"
        });
    } catch (error) {
        console.error("Error deleting conversation:", error);
        return res.status(500).json({
            success: false,
            message: "An error occurred while deleting the conversation.",
            error: error instanceof Error ? error.message : String(error),
        });
    }
}

export async function renameConversationHandler(req: Request, res: Response) {
    try {
        const userId = parseUserId(req.userId);
        const conversationId = parseConversationId(req.params.conversationId);
        const { title } = req.body;
        if (!userId) return res.status(401).json({ success: false, message: "Unauthorized access." });
        if (!conversationId) {
            return res.status(400).json({
                success: false,
                message: "Conversation ID is required.",
            });
        }
        if (!title) {
            return res.status(400).json({
                success: false,
                message: "Conversation title is required.",
            });
        }
        const conversation = await db.orm.public.Conversation
            .where({ id: conversationId, userId })
            .first();
        if (!conversation) {
            return res.status(404).json({
                success: false,
                message: "Conversation not found",
            });
        }
        const updatedConversation = await db.orm.public.Conversation
            .where({ id: conversationId })
            .update({ title, lastUpdated: new Date().toISOString() });
        if (!updatedConversation) {
            return res.status(404).json({ success: false, message: "Conversation not found" });
        }
        return res.status(200).json({
            success: true,
            message: "Conversation renamed successfully",
            data: updatedConversation,
        });
    } catch (error) {
        console.error("Error renaming conversation:", error);
        return res.status(500).json({
            success: false,
            message: "An error occurred while renaming the conversation.",
            error: error instanceof Error ? error.message : String(error),
        });
    }
}

export async function getConversationReportHandler(req: Request, res: Response) {
    try {
        const userId = parseUserId(req.userId);
        const conversationId = parseConversationId(req.params.conversationId);
        if (!userId) return res.status(401).json({ success: false, message: "Unauthorized access." });
        if (!conversationId) {
            return res.status(400).json({ success: false, message: "Conversation ID is required." });
        }
        const conversation = await db.orm.public.Conversation
            .where({ id: conversationId, userId })
            .first();
        if (!conversation) {
            return res.status(404).json({ success: false, message: "Conversation not found." });
        }
        const messages = await db.orm.public.Chat
            .where({ conversationId })
            .orderBy((chat) => chat.createdAt.asc())
            .all();
        const pdf = await createResearchPdf(conversation.title, messages);

        res.set({
            "Content-Type": "application/pdf",
            "Content-Disposition": `attachment; filename="socialverify-${conversationId}.pdf"`,
            "Content-Length": String(pdf.length),
        });
        return res.status(200).send(pdf);
    } catch (error) {
        console.error("Error generating conversation report:", error);
        return res.status(500).json({
            success: false,
            message: "The PDF report could not be generated.",
        });
    }
}
