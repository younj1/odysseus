
# ARIA Fine-tuning Script — Run this in a Python environment with Unsloth installed
# Prerequisites: pip install unsloth transformers datasets peft trl

import json
import torch
from unsloth import FastLanguageModel
from datasets import Dataset
from trl import SFTTrainer
from transformers import TrainingArguments

# Configuration
MODEL_NAME = "unsloth/Qwen2.5-7B-Instruct-bnb-4bit"
DATASET_PATH = "data/training_data.jsonl"
OUTPUT_DIR = "data/finetune_output"
MAX_SEQ_LENGTH = 2048
LORA_RANK = 16

# Load model with 4-bit quantization
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=MODEL_NAME,
    max_seq_length=MAX_SEQ_LENGTH,
    dtype=None,  # auto-detect
    load_in_4bit=True,
)

# Add LoRA adapters
model = FastLanguageModel.get_peft_model(
    model,
    r=LORA_RANK,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                     "gate_proj", "up_proj", "down_proj"],
    lora_alpha=16,
    lora_dropout=0,
    bias="none",
    use_gradient_checkpointing="unsloth",
)

# Load dataset
def load_jsonl(path):
    data = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))
    return data

raw_data = load_jsonl(DATASET_PATH)

# Format for chat template
def format_chat(example):
    messages = example["messages"]
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
    return {"text": text}

dataset = Dataset.from_list(raw_data)
dataset = dataset.map(format_chat)

# Training
trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=dataset,
    dataset_text_field="text",
    max_seq_length=MAX_SEQ_LENGTH,
    args=TrainingArguments(
        output_dir=OUTPUT_DIR,
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,
        warmup_steps=5,
        max_steps=60,
        learning_rate=2e-4,
        fp16=not torch.cuda.is_bf16_supported(),
        bf16=torch.cuda.is_bf16_supported(),
        logging_steps=1,
        save_strategy="steps",
        save_steps=30,
        seed=42,
    ),
)

print(f"Training on {len(dataset)} examples...")
trainer.train()

# Save
model.save_pretrained(f"{OUTPUT_DIR}/lora")
tokenizer.save_pretrained(f"{OUTPUT_DIR}/lora")
print(f"LoRA adapter saved to {OUTPUT_DIR}/lora")

# Merge and save full model for Ollama export
model.save_pretrained_merged(f"{OUTPUT_DIR}/merged", tokenizer, save_method="merged_16bit")
print(f"Merged model saved to {OUTPUT_DIR}/merged")
