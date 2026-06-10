"""Fine-tune a model using Unsloth (LoRA) on prepared training data."""

import os
import sys
import json
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

TRAIN_SCRIPT = """
# ARIA Fine-tuning Script — Run this in a Python environment with Unsloth installed
# Prerequisites: pip install unsloth transformers datasets peft trl

import json
import torch
from unsloth import FastLanguageModel
from datasets import Dataset
from trl import SFTTrainer
from transformers import TrainingArguments

# Configuration
MODEL_NAME = "{model_name}"
DATASET_PATH = "{dataset_path}"
OUTPUT_DIR = "{output_dir}"
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
    return {{"text": text}}

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

print(f"Training on {{len(dataset)}} examples...")
trainer.train()

# Save
model.save_pretrained(f"{{OUTPUT_DIR}}/lora")
tokenizer.save_pretrained(f"{{OUTPUT_DIR}}/lora")
print(f"LoRA adapter saved to {{OUTPUT_DIR}}/lora")

# Merge and save full model for Ollama export
model.save_pretrained_merged(f"{{OUTPUT_DIR}}/merged", tokenizer, save_method="merged_16bit")
print(f"Merged model saved to {{OUTPUT_DIR}}/merged")
"""


def generate_train_script(
    model_name: str = "unsloth/Qwen2.5-7B-Instruct-bnb-4bit",
    dataset_path: str = "data/training_data.jsonl",
    output_dir: str = "data/finetune_output",
) -> str:
    """Generate a training script that can be run with Unsloth."""
    
    script = TRAIN_SCRIPT.format(
        model_name=model_name,
        dataset_path=dataset_path,
        output_dir=output_dir,
    )
    
    script_path = "aria/finetune/run_training.py"
    with open(script_path, "w") as f:
        f.write(script)
    
    print(f"Training script generated: {script_path}")
    print(f"\nTo fine-tune, run these steps:")
    print(f"  1. Install Unsloth: pip install unsloth")
    print(f"  2. Prepare data: python aria/finetune/prepare_data.py")
    print(f"  3. Run training: python {script_path}")
    print(f"  4. Export to Ollama: python aria/finetune/export_ollama.py")
    
    return script_path


MODELFILE_TEMPLATE = """FROM {model_path}

PARAMETER temperature 0.7
PARAMETER top_p 0.9
PARAMETER num_predict 2000

SYSTEM "You are ARIA (Autonomous Retrieval & Intelligence Agent), a personal AI assistant.
You are thorough, accurate, and helpful. You specialize in coding and cybersecurity."
"""


def create_modelfile(
    model_path: str = "data/finetune_output/merged",
    output_path: str = "data/finetune_output/Modelfile",
) -> str:
    """Create an Ollama Modelfile for the fine-tuned model."""
    content = MODELFILE_TEMPLATE.format(model_path=model_path)
    with open(output_path, "w") as f:
        f.write(content)
    print(f"Modelfile created: {output_path}")
    print(f"\nTo import into Ollama:")
    print(f"  ollama create aria-custom -f {output_path}")
    return output_path


if __name__ == "__main__":
    generate_train_script()
